from http import HTTPStatus
from logging import getLogger
from typing import List, Tuple, Union

from flask import Flask, jsonify, request, Response as FlaskResponse
from flask_cors import CORS
from google.cloud import datastore
from werkzeug.datastructures import ImmutableMultiDict


logger = getLogger(__name__)
app = Flask(__name__)
CORS(app)
datastore_client = datastore.Client()


Response = Tuple[Union[FlaskResponse, str], HTTPStatus]


def _validate_input(input: ImmutableMultiDict) -> List[str]:
    return []


@app.route("/participants", methods=["GET"])
def participants() -> Response:
    """
    Serve an endpoint exposing the registered participants.

    :return: Json response.
    """
    query = datastore_client.query(kind="participant")
    participants = query.fetch()
    return jsonify(list(participants))


@app.route("/subscribe", methods=["POST"])
def subscribe() -> Response:
    """
    Serve an endpoint to subscribe to the tournament.

    :return: Json response.
    """
    errors = _validate_input(request.form)
    if errors:
        return "", HTTPStatus.BAD_REQUEST
    else:
        entity = datastore.Entity(key=datastore_client.key("participant"))
        entity.update(request.form)
        datastore_client.put(entity)
        return "", HTTPStatus.NO_CONTENT


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
