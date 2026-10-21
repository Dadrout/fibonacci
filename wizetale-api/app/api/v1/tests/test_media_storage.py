from app.services.media_storage import R2MediaStorage


class FakeR2Client:
    def __init__(self):
        self.uploads = []
        self.signed = []
        self.deleted = []
        self.pages = []

    def put_object(self, **kwargs):
        self.uploads.append(kwargs)

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        self.signed.append((operation, Params, ExpiresIn))
        return "https://r2.example/signed"

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        return self

    def paginate(self, **kwargs):
        self.pages.append(kwargs)
        return [{"Contents": [{"Key": "learner-1/job/video.mp4"}, {"Key": "learner-1/job/audio.mp3"}]}]

    def delete_objects(self, **kwargs):
        self.deleted.append(kwargs)
        return {"Errors": []}


def test_r2_uploads_private_asset_and_signs_short_lived_url(tmp_path, monkeypatch):
    client = FakeR2Client()
    storage = R2MediaStorage(client)
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video")
    monkeypatch.setattr("app.services.media_storage.settings.R2_BUCKET_NAME", "stories")
    monkeypatch.setattr("app.services.media_storage.settings.MEDIA_SIGNED_URL_TTL_SECONDS", 600)

    assert storage.upload(
        object_path="learner/job/video.mp4", local_path=str(media), content_type="video/mp4"
    ) == "learner/job/video.mp4"
    assert client.uploads[0]["ContentType"] == "video/mp4"
    assert storage.signed_url("learner/job/video.mp4") == "https://r2.example/signed"
    assert client.signed[0][2] == 600


def test_r2_rejects_signed_urls_longer_than_one_day():
    try:
        R2MediaStorage(FakeR2Client()).signed_url("private.mp4", 86401)
    except ValueError as error:
        assert "one day" in str(error)
    else:
        raise AssertionError("Expected overly long signed URL TTL to be rejected")


def test_r2_deletes_only_the_user_asset_prefix(monkeypatch):
    client = FakeR2Client()
    storage = R2MediaStorage(client)
    monkeypatch.setattr("app.services.media_storage.settings.R2_BUCKET_NAME", "stories")

    count = storage.delete_user_assets("learner-1")

    assert count == 2
    assert client.pages == [{"Bucket": "stories", "Prefix": "learner-1/"}]
    assert client.deleted[0]["Delete"]["Objects"] == [
        {"Key": "learner-1/job/video.mp4"},
        {"Key": "learner-1/job/audio.mp3"},
    ]


def test_r2_deletes_only_the_cancelled_job_prefix(monkeypatch):
    client = FakeR2Client()
    storage = R2MediaStorage(client)
    monkeypatch.setattr("app.services.media_storage.settings.R2_BUCKET_NAME", "stories")

    assert storage.delete_job_assets("learner-1", "job") == 2
    assert client.pages == [{"Bucket": "stories", "Prefix": "learner-1/job/"}]
    assert client.deleted[0]["Delete"]["Objects"] == [
        {"Key": "learner-1/job/video.mp4"},
        {"Key": "learner-1/job/audio.mp3"},
    ]
