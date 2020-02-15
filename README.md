# Nantes Go Tournament Website Server

Google App that uses Flask to provide two endpoints: one to subscribe to the event, the other to list participants.

## Deploying

To deploy, first create a credentials file on the [Google Cloud Console](https://console.cloud.google.com/apis/credentials), then save it as `owner-credentials.json` in this folder.

The first time, you have [install `gcloud`](https://cloud.google.com/sdk/docs/quickstarts).
You then have to set it up correctly for the tournament project:

    gcloud auth login
    gcloud config set project nantes-tournament

Once `gcloud` is properly set up, you deploy with:

    source env.sh
    gcloud app deploy
