import s3


def test_generate_presigned_url():
    s3.create_presigned_urls_multipart("landingzone", "testdataset/testimage.img", 2)
