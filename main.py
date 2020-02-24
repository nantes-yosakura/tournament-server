from http import HTTPStatus
from logging import getLogger
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
from werkzeug import Response as WerkzeugResponse
from wtforms import Field, Form, RadioField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length


logger = getLogger(__name__)
app = Flask(__name__)
app.config.from_pyfile("secret_key.py")
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
                message="La taille de ce courriel doit être de %(min)d à %(max)d "
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
                message="La taille de ce courriel doit être de %(min)d à %(max)d "
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
                message="La taille de ce courriel doit être de %(min)d à %(max)d "
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
        "Niveau (si vous vous inscrivez comme joueur⋅se)",
        choices=_levels,
        validators=[
            DataRequiredIf(
                "subscription",
                "player",
                message="Ce champ est obligatoire si vous êtes inscrit⋅e comme "
                "joueur⋅se.",
            )
        ],
    )
    club = StringField(
        "Club (si vous vous inscrivez comme joueur⋅se)",
        description="Exemple: 44Na",
        validators=[
            DataRequiredIf(
                "subscription",
                "player",
                message="Ce champ est obligatoire si vous êtes inscrit⋅e comme "
                "joueur⋅se.",
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
        entity = datastore.Entity(key=datastore_client.key("participant"))
        entity.update(
            {
                "first-name": form.first_name.data,
                "last-name": form.last_name.data,
                "email": form.email.data,
                "type": form.subscription.data,
            }
        )
        if form.subscription.data == "player":
            entity.update({"level": form.level.data, "club": form.club.data})
        app.logger.info("Persisting %s", entity)
        datastore_client.put(entity)
        return redirect("/confirmation", code=HTTPStatus.FOUND)
    return render_template("index.html", form=form)


@app.route("/confirmation", methods=["GET"])
def confirmation() -> Response:
    """
    Serve the confirmation page.

    :return: Confirmation page.
    """
    return render_template("confirmation.html")


@app.route("/participants", methods=["GET"])
def participants() -> Response:
    """
    Serve an endpoint exposing the registered participants.

    :return: Json response.
    """
    query = datastore_client.query(kind="participant")
    participants = query.fetch()
    return jsonify(list(participants))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
