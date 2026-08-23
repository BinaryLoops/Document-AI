"""
One-off script: seeds the Digital Locker with realistic, fully-verified demo
documents for the demo citizen account, so "My Documents" is never empty in
a fresh demo/install.

Run with:
    python scripts/seed_demo_documents.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from digilocker.database import DocumentDatabase
from digilocker.models import DocumentCategory, DocumentLifecycle, LockerDocument, VerificationStatus

OWNER = "demo-citizen-001"
NOW = datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return NOW - timedelta(days=n)


DEMO_DOCUMENTS = [
    dict(
        department="Municipal Corporation of Delhi",
        document_type=DocumentCategory.BIRTH_CERTIFICATE,
        serial_number="BC-2023-0045678",
        original_filename="birth_certificate_rahul_sharma.pdf",
        mime_type="application/pdf",
        file_size=284_112,
        page_count=1,
        confidence_score=0.96,
        ocr_text=(
            "GOVERNMENT OF NCT OF DELHI\nMUNICIPAL CORPORATION OF DELHI\n"
            "BIRTH CERTIFICATE\n\nThis is to certify that the following details "
            "have been taken from the original record of birth.\n\n"
            "Name: Rahul Sharma\nDate of Birth: 15/08/1995\nSex: Male\n"
            "Name of Father: Suresh Sharma\nName of Mother: Anita Sharma\n"
            "Place of Birth: Safdarjung Hospital, New Delhi\n"
            "Registration Number: BC-2023-0045678\nDate of Registration: 20/08/1995\n"
            "Issuing Authority: Municipal Corporation of Delhi"
        ),
        extracted_metadata={
            "document_title": "BIRTH CERTIFICATE",
            "holder_name": "Rahul Sharma",
            "date_of_birth": "15/08/1995",
            "father_name": "Suresh Sharma",
            "mother_name": "Anita Sharma",
            "place": "Safdarjung Hospital, New Delhi",
            "certificate_number": "BC-2023-0045678",
            "issue_date": "20/08/1995",
            "issuing_authority": "Municipal Corporation of Delhi",
        },
        upload_days_ago=120,
    ),
    dict(
        department="Regional Passport Office, New Delhi",
        document_type=DocumentCategory.PASSPORT,
        serial_number="P1234567",
        original_filename="passport_rahul_sharma.pdf",
        mime_type="application/pdf",
        file_size=612_480,
        page_count=2,
        confidence_score=0.94,
        ocr_text=(
            "REPUBLIC OF INDIA\nPASSPORT\n\nType: P  Country Code: IND\n"
            "Passport No: P1234567\nSurname: SHARMA\nGiven Name: RAHUL\n"
            "Date of Birth: 15/08/1995\nSex: M\nPlace of Birth: NEW DELHI\n"
            "Date of Issue: 12/03/2021\nDate of Expiry: 11/03/2031\n"
            "Place of Issue: NEW DELHI\nIssuing Authority: Regional Passport Office, New Delhi"
        ),
        extracted_metadata={
            "document_title": "PASSPORT",
            "holder_name": "Rahul Sharma",
            "passport_number": "P1234567",
            "date_of_birth": "15/08/1995",
            "issue_date": "12/03/2021",
            "expiry_date": "11/03/2031",
            "issuing_authority": "Regional Passport Office, New Delhi",
        },
        upload_days_ago=95,
    ),
    dict(
        department="Transport Department, Government of NCT of Delhi",
        document_type=DocumentCategory.DRIVING_LICENCE,
        serial_number="DL-0420230012345",
        original_filename="driving_licence_rahul_sharma.pdf",
        mime_type="application/pdf",
        file_size=198_004,
        page_count=1,
        confidence_score=0.93,
        ocr_text=(
            "GOVERNMENT OF NCT OF DELHI\nTRANSPORT DEPARTMENT\n"
            "DRIVING LICENCE\n\nDL No: DL-0420230012345\nName: Rahul Sharma\n"
            "Date of Birth: 15/08/1995\nBlood Group: B+\n"
            "Date of Issue: 05/06/2022\nValid Till: 04/06/2042\n"
            "Class of Vehicle: LMV, MCWG\nIssuing Authority: Transport Department, Delhi"
        ),
        extracted_metadata={
            "document_title": "DRIVING LICENCE",
            "holder_name": "Rahul Sharma",
            "license_number": "DL-0420230012345",
            "issue_date": "05/06/2022",
            "expiry_date": "04/06/2042",
            "issuing_authority": "Transport Department, Delhi",
        },
        upload_days_ago=60,
    ),
    dict(
        department="Office of the Tehsildar, South Delhi",
        document_type=DocumentCategory.INCOME_CERTIFICATE,
        serial_number="INC-2024-778812",
        original_filename="income_certificate_rahul_sharma.pdf",
        mime_type="application/pdf",
        file_size=156_233,
        page_count=1,
        confidence_score=0.91,
        ocr_text=(
            "GOVERNMENT OF NCT OF DELHI\nOFFICE OF THE TEHSILDAR, SOUTH DELHI\n"
            "INCOME CERTIFICATE\n\nCertificate No: INC-2024-778812\n"
            "This is to certify that Rahul Sharma S/o Suresh Sharma, resident of "
            "New Delhi, has an annual family income of Rs. 4,50,000/- "
            "(Rupees Four Lakh Fifty Thousand only) for the financial year 2023-24.\n"
            "Issue Date: 10/01/2024\nIssuing Authority: Tehsildar, South Delhi"
        ),
        extracted_metadata={
            "document_title": "INCOME CERTIFICATE",
            "holder_name": "Rahul Sharma",
            "father_name": "Suresh Sharma",
            "reference_number": "INC-2024-778812",
            "amount": "4,50,000",
            "issue_date": "10/01/2024",
            "issuing_authority": "Tehsildar, South Delhi",
        },
        upload_days_ago=30,
    ),
    dict(
        department="Central Board of Secondary Education",
        document_type=DocumentCategory.EDUCATION_CERTIFICATE,
        serial_number="CBSE-2013-1122334",
        original_filename="education_certificate_rahul_sharma.pdf",
        mime_type="application/pdf",
        file_size=221_875,
        page_count=1,
        confidence_score=0.95,
        ocr_text=(
            "CENTRAL BOARD OF SECONDARY EDUCATION\nCERTIFICATE OF EDUCATION\n\n"
            "This is to certify that Rahul Sharma, Roll No. 1122334, has passed "
            "the Senior School Certificate Examination (Class XII) held in "
            "March 2013 securing 89.4% marks.\n"
            "Certificate No: CBSE-2013-1122334\nDate of Issue: 28/05/2013\n"
            "Issuing Authority: Central Board of Secondary Education"
        ),
        extracted_metadata={
            "document_title": "CERTIFICATE OF EDUCATION",
            "holder_name": "Rahul Sharma",
            "roll_number": "1122334",
            "certificate_number": "CBSE-2013-1122334",
            "issue_date": "28/05/2013",
            "issuing_authority": "Central Board of Secondary Education",
            "percentage": "89.4%",
        },
        upload_days_ago=15,
    ),
    dict(
        department="Revenue Department, Government of NCT of Delhi",
        document_type=DocumentCategory.LAND_RECORD,
        serial_number="LR-KH-234-5",
        original_filename="land_record_rahul_sharma.pdf",
        mime_type="application/pdf",
        file_size=312_998,
        page_count=3,
        confidence_score=0.89,
        ocr_text=(
            "REVENUE DEPARTMENT\nRECORD OF RIGHTS (KHASRA)\n\n"
            "Khasra No: 234/5\nVillage: Rampur\nOwner: Rahul Sharma\n"
            "Area: 0.45 Hectares\nLand Use: Residential\n"
            "Date of Mutation: 02/02/2024\nIssuing Authority: Revenue Department, Delhi"
        ),
        extracted_metadata={
            "document_title": "RECORD OF RIGHTS (KHASRA)",
            "holder_name": "Rahul Sharma",
            "khasra_number": "234/5",
            "place": "Rampur",
            "issue_date": "02/02/2024",
            "issuing_authority": "Revenue Department, Delhi",
        },
        upload_days_ago=5,
    ),
]


async def main():
    db = DocumentDatabase()
    await db.initialise()

    existing = await db.list_documents(owner=OWNER, limit=200)
    existing_serials = {d.serial_number for d in existing}

    created = 0
    for spec in DEMO_DOCUMENTS:
        if spec["serial_number"] in existing_serials:
            print(f"Skip (already exists): {spec['serial_number']}")
            continue
        uploaded = days_ago(spec.pop("upload_days_ago"))
        doc = LockerDocument(
            owner=OWNER,
            department=spec["department"],
            document_type=spec["document_type"],
            serial_number=spec["serial_number"],
            verification_status=VerificationStatus.VERIFIED,
            confidence_score=spec["confidence_score"],
            original_filename=spec["original_filename"],
            file_size=spec["file_size"],
            mime_type=spec["mime_type"],
            page_count=spec["page_count"],
            ocr_text=spec["ocr_text"],
            extracted_metadata=spec["extracted_metadata"],
            lifecycle=DocumentLifecycle.ACTIVE,
            upload_timestamp=uploaded,
            updated_at=uploaded,
        )
        await db.insert_document(doc)
        created += 1
        print(f"Seeded: {spec['document_type'].value} ({spec['serial_number']})")

    await db.close()
    print(f"\nDone. {created} new document(s) seeded, {len(existing_serials)} already present.")


if __name__ == "__main__":
    asyncio.run(main())
