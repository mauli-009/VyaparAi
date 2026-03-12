import uuid
import os

UPLOAD_FOLDER = "uploads"

def generate_file_id():
    return str(uuid.uuid4())

def save_uploaded_file(file, file_id):
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}.csv")

    # Read bytes properly from UploadFile (sync context)
    contents = file.file.read()
    with open(file_path, "wb") as buffer:
        buffer.write(contents)

    # Reset file pointer in case it's reused
    file.file.seek(0)

    return file_path