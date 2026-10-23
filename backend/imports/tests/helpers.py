from django.core.files.uploadedfile import SimpleUploadedFile

URL = "/api/v1/institution/imports"
HEADER = (
    "source_record_id,full_name,date_of_birth,phone,email,address,admitted_on,academic_year,place_code,place_label,"
    "campus_code,entry_date,guardian_name,guardian_relationship,guardian_phone,guardian_email"
)


def line(source="S-1", name="Kiran Rao", born="2019-04-02", **changes) -> str:
    values = {
        "source_record_id": source,
        "full_name": name,
        "date_of_birth": born,
        "phone": "",
        "email": "",
        "address": "7 Lake Road",
        "admitted_on": "2024-06-01",
        "academic_year": "2026–27",
        "place_code": "C2",
        "place_label": "Class 2",
        "campus_code": "MAIN",
        "entry_date": "2026-06-01",
        "guardian_name": "Lata Rao",
        "guardian_relationship": "Mother",
        "guardian_phone": "+91 90000 33333",
        "guardian_email": "",
        **changes,
    }
    return ",".join(values[column] for column in HEADER.split(","))


def csv_file(*lines: str, header: str = HEADER, name: str = "students.csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, "\n".join([header, *lines]).encode(), content_type="text/csv")


def upload(client, file, source_system="Old ERP"):
    return client.post(URL, {"file": file, "source_system": source_system}, format="multipart")
