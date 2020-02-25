from http import HTTPStatus
from logging import getLogger
from secrets import token_urlsafe
from typing import Any, Tuple, Union

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    Response as FlaskResponse,
)
from flask_bootstrap import Bootstrap
from flask_cors import CORS
from flask_wtf import FlaskForm
from google.cloud import datastore
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from sendgrid.helpers.mail import ReplyTo
from werkzeug import Response as WerkzeugResponse
from wtforms import Field, Form, RadioField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length


logger = getLogger(__name__)
app = Flask(__name__)
app.config.from_pyfile("config_secrets.py")
Bootstrap(app)
CORS(app)
datastore_client = datastore.Client()


HttpResponse = Union[FlaskResponse, WerkzeugResponse, str]
Response = Union[HttpResponse, Tuple[Union[HttpResponse, str], HTTPStatus]]


_levels = (
    [("", "---")]
    + [("%dk" % i, "%d Kyu" % i) for i in range(30, 0, -1)]
    + [("%dd" % i, "%d Dan" % i) for i in range(1, 9)]
    + [("%dp" % i, "%d Dan Pro" % i) for i in range(1, 10)]
)


class DataRequiredIf:
    """DataRequired on a field if another field has a given value."""

    def __init__(
        self, other_field_name: str, other_field_data: Any, *args: Any, **kwargs: Any
    ) -> None:
        """Initialize an underlying DataRequired and the conditions to apply it."""
        self.data_required = DataRequired(*args, **kwargs)
        self.other_field_name = other_field_name
        self.other_field_data = other_field_data

    def __call__(self, form: Form, field: Field) -> None:
        """Apply a DataRequired if another field has a given value."""
        other_field = form._fields.get(self.other_field_name)
        if other_field is None:
            raise Exception('No field named "%s" in form' % self.other_field_name)
        if other_field.data == self.other_field_data:
            self.data_required(form, field)


class SubscriptionForm(FlaskForm):
    """Subscription form."""

    first_name = StringField(
        "Prénom",
        description="Exemple: Lila",
        validators=[
            DataRequired("Ce champ est obligatoire."),
            Length(
                message="La taille de ce champ est limitée de %(min)d à %(max)d "
                "caractères.",
                min=1,
                max=100,
            ),
        ],
    )
    last_name = StringField(
        "Nom",
        description="Exemple: Zéreau",
        validators=[
            DataRequired("Ce champ est obligatoire."),
            Length(
                message="La taille de ce champ est limitée de %(min)d à %(max)d "
                "caractères.",
                min=1,
                max=100,
            ),
        ],
    )
    email = StringField(
        "Courriel",
        description="Exemple: lila.zereau@lizzie.org",
        validators=[
            DataRequired("Ce champ est obligatoire."),
            Email("Ce courriel est invalide."),
            Length(
                message="La taille de ce champ est limitée de %(min)d à %(max)d "
                "caractères.",
                min=6,
                max=100,
            ),
        ],
    )
    subscription = RadioField(
        "Type",
        choices=[("player", "Joueur⋅se"), ("non-player", "Accompagnateur⋅rice")],
        validators=[DataRequired("Ce champ est obligatoire.")],
    )
    level = SelectField(
        "Niveau (si tu t'inscris comme joueur⋅se)",
        choices=_levels,
        validators=[
            DataRequiredIf(
                "subscription",
                "player",
                message="Ce champ est obligatoire si tu t'inscris comme joueur⋅se.",
            )
        ],
    )
    club = StringField(
        "Club (si tu t'inscris comme joueur⋅se)",
        description="Exemple: 44Na",
        validators=[
            DataRequiredIf(
                "subscription",
                "player",
                message="Ce champ est obligatoire si tu t'inscris comme joueur⋅se.",
            )
        ],
    )
    submit = SubmitField("S'inscrire")


@app.route("/", methods=["GET", "POST"])
def index() -> Response:
    """
    Serve the subscription page.

    :return: Subscription page or redirect to success page.
    """
    form = SubscriptionForm()
    if form.validate_on_submit():
        first_name = form.first_name.data
        last_name = form.last_name.data
        email = form.email.data
        subscription = form.subscription.data
        level = form.level.data
        club = form.club.data
        salt = token_urlsafe(32)
        entity = datastore.Entity(key=datastore_client.key("participants"))
        entity.update(
            {
                "pending": True,
                "salt": salt,
                "first-name": first_name,
                "last-name": last_name,
                "email": email,
                "type": subscription,
            }
        )
        if subscription == "player":
            entity.update({"level": level, "club": club})
        app.logger.info("Persisting %s", entity)
        datastore_client.put(entity)
        key_id = entity.id
        pending_email = Mail(
            from_email="ne-pas-repondre@em5405.crydee.eu",
            to_emails=email,
            subject="Inscription en cours de validation pour le tournoi de Nantes 2020",
            plain_text_content=render_template("pending.email.jinja2", name=first_name),
        )
        pending_email.reply_to = ReplyTo(
            "clubyosakura@yahoo.fr", "Club Nantes Yosakura"
        )
        admin_email = Mail(
            from_email="ne-pas-repondre@em5405.crydee.eu",
            to_emails="mog@crydee.eu",
            subject="Validation d'inscription nécessaire",
            plain_text_content=render_template(
                "admin.email.jinja2",
                first_name=first_name,
                last_name=last_name,
                email=email,
                subscription=subscription,
                level=level,
                club=club,
                salt=salt,
                key_id=key_id,
            ),
        )
        pending_email.reply_to = ReplyTo(
            "clubyosakura@yahoo.fr", "Club Nantes Yosakura"
        )
        try:
            sendgrid_client = SendGridAPIClient(app.config["SENDGRID_API_KEY"])
            pending_response = sendgrid_client.send(pending_email)
            app.logger.info(
                "Sent pending email to %s with status %d",
                email,
                pending_response.status_code,
            )
            admin_response = sendgrid_client.send(admin_email)
            app.logger.info(
                "Sent admin email with status %d", admin_response.status_code,
            )
        except Exception as e:
            app.logger.error("Could not send emails, with exception: %s", e)
        return redirect("/en-attente", code=HTTPStatus.FOUND)
    return render_template("index.html.jinja2", form=form)


@app.route("/en-attente", methods=["GET"])
def pending() -> Response:
    """
    Serve the pending validation page.

    :return: Pending validation page.
    """
    return render_template("pending.html.jinja2")


@app.route("/confirm/<int:key_id>/<string:salt>", methods=["GET"])
def confirm(key_id: int, salt: str) -> Response:
    """
    Serve the confirmation page.

    :return: Confirmation page.
    """
    entity = datastore_client.get(datastore_client.key("participants", key_id))
    if entity.get("salt") == salt:
        entity.update({"pending": False})
        datastore_client.put(entity)
        email = entity.get("email")
        first_name = entity.get("first-name")
        confirm_email = Mail(
            from_email="ne-pas-repondre@em5405.crydee.eu",
            to_emails=email,
            subject="Validation d'inscription",
            plain_text_content=render_template("confirm.email.jinja2", name=first_name),
        )
        confirm_email.reply_to = ReplyTo(
            "clubyosakura@yahoo.fr", "Club Nantes Yosakura"
        )
        try:
            sendgrid_client = SendGridAPIClient(app.config["SENDGRID_API_KEY"])
            pending_response = sendgrid_client.send(confirm_email)
            app.logger.info(
                "Sent confirm email to %s with status %d",
                email,
                pending_response.status_code,
            )
        except Exception as e:
            app.logger.error("Could not send confirm email, with exception: %s", e)
        return render_template("confirm.html.jinja2", success=True)
    return render_template("confirm.html.jinja2", success=False)


@app.route("/participants", methods=["GET"])
def participants() -> Response:
    """
    Serve an endpoint exposing the registered participants.

    :return: Json response.
    """
    query = datastore_client.query(kind="participants")
    query.add_filter("pending", "=", False)
    participants = query.fetch()
    return jsonify(list(participants))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
