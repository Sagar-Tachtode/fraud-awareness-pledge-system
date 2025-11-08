"""
Fraud Awareness Week - Integrity Pledge System
Lambda Function with S3 CSV Employee Loading & 5-min Caching
For 3000 Employees - Production Ready

Author: Fraud Awareness Week Team
Date: November 2025
Version: 1.0
"""

import json
import boto3
import os
import csv
from datetime import datetime
from io import BytesIO, StringIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
import uuid

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables
EMPLOYEES_BUCKET = os.environ.get('EMPLOYEES_BUCKET', 'employee-data-bucket')
EMPLOYEES_FILE = os.environ.get('EMPLOYEES_FILE', 'employees.csv')
S3_CERT_BUCKET = os.environ.get('S3_CERT_BUCKET', 'certificates-bucket')
PLEDGES_TABLE = os.environ.get('PLEDGES_TABLE', 'fraud-awareness-pledges')

pledges_table = dynamodb.Table(PLEDGES_TABLE)

# Global cache variables
_employees_cache = None
_cache_timestamp = None

def load_employees_from_s3():
    """Load employee data from S3 CSV file with 5-minute caching"""
    global _employees_cache, _cache_timestamp

    now = datetime.now()

    # Check if cache is still valid (5 minutes)
    if _employees_cache and _cache_timestamp:
        cache_age = (now - _cache_timestamp).total_seconds()
        if cache_age < 300:  # 5 minute cache
            print(f"✓ Using cached employees ({len(_employees_cache)} employees)")
            return _employees_cache

    try:
        print(f"Loading employees from S3: s3://{EMPLOYEES_BUCKET}/{EMPLOYEES_FILE}")

        # Download CSV from S3
        response = s3_client.get_object(Bucket=EMPLOYEES_BUCKET, Key=EMPLOYEES_FILE)
        csv_content = response['Body'].read().decode('utf-8')

        # Parse CSV
        csv_reader = csv.DictReader(StringIO(csv_content))
        employees = {}

        for row in csv_reader:
            employee_id = row.get('employee_id', '').strip()
            if employee_id:
                employees[employee_id] = {
                    'employee_id': employee_id,
                    'employee_name': row.get('employee_name', '').strip(),
                    'department': row.get('department', '').strip(),
                    'email': row.get('email', '').strip(),
                    'designation': row.get('designation', '').strip(),
                }

        # Cache the results
        _employees_cache = employees
        _cache_timestamp = now

        print(f"✓ Loaded {len(employees)} employees from S3")
        return employees

    except Exception as e:
        print(f"✗ Error loading employees from S3: {e}")
        raise

def get_employee_details(employee_id):
    """Get employee details from cached data"""
    employees = load_employees_from_s3()
    return employees.get(employee_id)

def save_pledge_record(employee_id, employee_name, department):
    """Save pledge to DynamoDB"""
    try:
        pledge_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        pledges_table.put_item(
            Item={
                'pledge_id': pledge_id,
                'employee_id': employee_id,
                'employee_name': employee_name,
                'department': department,
                'pledge_date': timestamp,
                'certificate_generated': True,
                'status': 'completed',
                'created_at': timestamp
            }
        )

        print(f"✓ Pledge saved for {employee_id}")
        return pledge_id
    except Exception as e:
        print(f"✗ Error saving pledge: {e}")
        raise

def generate_certificate_pdf(employee_name, employee_id, department):
    """Generate professional PDF certificate"""

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    # Background
    pdf.setFillColorRGB(0.95, 0.95, 1.0)
    pdf.rect(0, 0, width, height, fill=True, stroke=False)

    # Decorative borders
    pdf.setStrokeColorRGB(0.4, 0.5, 0.9)
    pdf.setLineWidth(8)
    pdf.rect(30, 30, width-60, height-60, fill=False, stroke=True)

    pdf.setStrokeColorRGB(0.5, 0.6, 1.0)
    pdf.setLineWidth(3)
    pdf.rect(40, 40, width-80, height-80, fill=False, stroke=True)

    # Corner decorations
    corner_size = 50
    pdf.setStrokeColorRGB(0.6, 0.4, 0.8)
    pdf.setLineWidth(5)
    for x_pos, y_pos in [(50, height-50), (width-50, height-50), (50, 50), (width-50, 50)]:
        pdf.line(x_pos, y_pos, min(x_pos + corner_size, width-10), y_pos)
        pdf.line(x_pos, y_pos, x_pos, y_pos + corner_size if y_pos < height/2 else y_pos - corner_size)

    # Title
    pdf.setFillColorRGB(0.2, 0.2, 0.5)
    pdf.setFont("Helvetica-Bold", 36)
    pdf.drawCentredString(width/2, height-100, "CERTIFICATE OF INTEGRITY")

    # Subtitle
    pdf.setFillColorRGB(0.8, 0.2, 0.2)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(width/2, height-140, "Fraud Awareness Week")

    # Decorative line
    pdf.setStrokeColorRGB(0.6, 0.4, 0.8)
    pdf.setLineWidth(2)
    pdf.line(width/2-200, height-155, width/2+200, height-155)

    # Body text
    pdf.setFillColorRGB(0.2, 0.2, 0.2)
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(width/2, height-200, "This certifies that")

    # Employee name
    pdf.setFillColorRGB(0.1, 0.1, 0.5)
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(width/2, height-240, employee_name.upper())

    # Employee details
    pdf.setFillColorRGB(0.3, 0.3, 0.3)
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(width/2, height-270, f"Employee ID: {employee_id} | Department: {department}")

    # Pledge content
    pdf.setFillColorRGB(0.2, 0.2, 0.2)
    pdf.setFont("Helvetica", 13)
    y_position = height - 320

    pledge_lines = [
        "has taken the Integrity Pledge and commits to:",
        "",
        "• Protecting the company's integrity and reputation",
        "• Staying alert and questioning what feels wrong",
        "• Always choosing ethics over convenience",
        "• Ensuring every customer can trust our promise",
        "• Contributing to a culture of honesty and accountability"
    ]

    for line in pledge_lines:
        if line.startswith("•"):
            pdf.setFont("Helvetica-Bold", 12)
        else:
            pdf.setFont("Helvetica", 13)
        pdf.drawCentredString(width/2, y_position, line)
        y_position -= 25

    # Date and signature
    pdf.setFont("Helvetica", 11)
    pdf.setFillColorRGB(0.3, 0.3, 0.3)
    date_str = datetime.now().strftime("%B %d, %Y")
    pdf.drawString(100, 120, f"Date: {date_str}")

    # Signature line
    pdf.setLineWidth(1)
    pdf.setStrokeColorRGB(0.5, 0.5, 0.5)
    pdf.line(width-300, 120, width-100, 120)
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(width-200, 105, "Authorized Signature")

    # Footer
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.setFillColorRGB(0.5, 0.5, 0.5)
    pdf.drawCentredString(width/2, 50, "Building Trust Through Integrity")
    pdf.drawCentredString(width/2, 35, "© 2025 Your Insurance Company. All Rights Reserved.")

    # Certificate ID
    cert_id = f"FAW-{datetime.now().strftime('%Y%m%d')}-{employee_id}"
    pdf.setFont("Courier", 8)
    pdf.drawString(50, 20, f"Certificate ID: {cert_id}")

    pdf.save()
    buffer.seek(0)
    return buffer

def upload_to_s3(file_buffer, employee_id):
    """Upload certificate to S3 and return presigned URL"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    s3_key = f"certificates/{employee_id}_{timestamp}.pdf"

    try:
        s3_client.put_object(
            Bucket=S3_CERT_BUCKET,
            Key=s3_key,
            Body=file_buffer.getvalue(),
            ContentType='application/pdf'
        )

        print(f"✓ Certificate uploaded to S3: {s3_key}")

        # Generate presigned URL (valid for 1 hour)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_CERT_BUCKET, 'Key': s3_key},
            ExpiresIn=3600
        )

        return url
    except Exception as e:
        print(f"✗ S3 upload error: {e}")
        raise

def lambda_handler(event, context):
    """Main Lambda handler - processes pledge submissions"""

    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'POST,OPTIONS'
    }

    # Handle CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'OK'})
        }

    try:
        print(f"Received event: {json.dumps(event)}")

        # Parse request body
        body = json.loads(event.get('body', '{}'))
        employee_id = body.get('employee_id', '').strip()

        if not employee_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'success': False,
                    'message': 'Employee ID is required'
                })
            }

        # Get employee from S3 CSV (cached)
        print(f"Looking up employee: {employee_id}")
        employee = get_employee_details(employee_id)

        if not employee:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'success': False,
                    'message': f'Employee ID {employee_id} not found'
                })
            }

        employee_name = employee.get('employee_name')
        department = employee.get('department', 'N/A')

        print(f"Generating certificate for: {employee_name}")

        # Generate PDF certificate
        pdf_buffer = generate_certificate_pdf(employee_name, employee_id, department)

        # Upload to S3
        certificate_url = upload_to_s3(pdf_buffer, employee_id)

        # Save pledge record to DynamoDB
        pledge_id = save_pledge_record(employee_id, employee_name, department)

        print(f"✓ Pledge processed successfully for {employee_id}")

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'success': True,
                'message': 'Pledge submitted successfully',
                'employee_name': employee_name,
                'certificate_url': certificate_url,
                'pledge_id': pledge_id
            })
        }

    except Exception as e:
        print(f"✗ Error in lambda_handler: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'success': False,
                'message': f'Internal server error: {str(e)}'
            })
        }
