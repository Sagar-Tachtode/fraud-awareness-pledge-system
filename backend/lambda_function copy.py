import json
import boto3
import csv
import os
from datetime import datetime
from io import StringIO, BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
import uuid
import base64

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'pledge-certificate-generation-project')
CSV_KEY = os.environ.get('CSV_KEY', 'employees.csv')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'IntegrityPledges')

# In-memory cache
employee_cache = {'data': None, 'timestamp': None}
CACHE_TTL = 300

def load_employees_from_s3():
    """Load employee data from S3 CSV with caching"""
    global employee_cache
    current_time = datetime.now().timestamp()
    
    if employee_cache['data'] and employee_cache['timestamp']:
        if current_time - employee_cache['timestamp'] < CACHE_TTL:
            print(f"✓ Using cached employee data ({len(employee_cache['data'])} employees)")
            return employee_cache['data']
    
    print(f"Loading employees from S3: s3://{BUCKET_NAME}/{CSV_KEY}")
    
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=CSV_KEY)
        csv_content = response['Body'].read().decode('utf-8')
        csv_reader = csv.DictReader(StringIO(csv_content))
        employees = {row['employee_id']: row for row in csv_reader}
        employee_cache['data'] = employees
        employee_cache['timestamp'] = current_time
        print(f"✓ Loaded {len(employees)} employees from S3")
        return employees
    except Exception as e:
        print(f"✗ Error loading employees: {str(e)}")
        raise

def generate_certificate_pdf(employee_name, employee_id, department, designation, pledge_date=None):
    """Generate professional horizontal PDF certificate"""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    # Soft background
    pdf.setFillColorRGB(0.95, 0.95, 1.0)
    pdf.rect(0, 0, width, height, fill=True, stroke=False)

    # Borders
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
        if y_pos < height / 2:
            pdf.line(x_pos, y_pos, x_pos, y_pos + corner_size)
        else:
            pdf.line(x_pos, y_pos, x_pos, y_pos - corner_size)

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
    pdf.drawCentredString(width/2, height-270, f"Employee ID: {employee_id} | Department: {department} | Designation: {designation}")

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

    # Date and signature  (bottom left)
    pdf.setFont("Helvetica", 11)
    pdf.setFillColorRGB(0.3, 0.3, 0.3)
    date_str = datetime.now().strftime("%B %d, %Y")
    pdf.drawString(100, 80, f"Date of Pledge: {date_str}")

    # Signature line
    pdf.setLineWidth(1)
    pdf.setStrokeColorRGB(0.5, 0.5, 0.5)
    pdf.line(width-300, 80, width-100, 80)
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(width-200, 105, "Authorized Signature")

    # Footer
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.setFillColorRGB(0.5, 0.5, 0.5)
    pdf.drawCentredString(width/2, 65, "Building Trust Through Integrity")
    pdf.drawCentredString(width/2, 50, "© 2025 Edelweiss Life Insurance. All Rights Reserved.")

    # Certificate ID
    cert_id = f"FAW-{datetime.now().strftime('%Y%m%d')}-{employee_id}"
    pdf.setFont("Courier", 8)
    pdf.drawString(50, 20, f"Certificate ID: {cert_id}")

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()

def save_pledge_to_dynamodb(employee_id, employee_name, department, designation, pledge_id):
    """Save pledge to DynamoDB"""
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        item = {
            'pledge_id': pledge_id,
            'employee_id': employee_id,
            'employee_name': employee_name,
            'department': department,
            'designation': designation,
            'pledge_timestamp': datetime.now().isoformat(),
            'status': 'completed'
        }
        table.put_item(Item=item)
        print(f"✓ Pledge saved to DynamoDB for {employee_id}")
    except Exception as e:
        print(f"⚠ DynamoDB save failed (non-critical): {str(e)}")

def lambda_handler(event, context):
    """Main Lambda handler - CORS handled by Function URL"""
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        employee_id = body.get('employee_id')
        pledge_accepted = body.get('pledge_accepted', False)
        
        # Validation
        if not employee_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},  # Only Content-Type
                'body': json.dumps({'success': False, 'message': 'Employee ID is required'})
            }
        
        if not pledge_accepted:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'message': 'Pledge must be accepted'})
            }
        
        # Load employee data
        print(f"Looking up employee: {employee_id}")
        employees = load_employees_from_s3()
        
        if employee_id not in employees:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'message': f'Employee {employee_id} not found'})
            }
        
        employee = employees[employee_id]
        employee_name = employee['employee_name']
        department = employee.get('department', 'N/A')
        designation = employee.get('designation', 'N/A')
        
        # Generate certificate
        date_str = datetime.now().strftime("%B %d, %Y")
        pdf_bytes = generate_certificate_pdf(employee_name, employee_id, department, designation, date_str)
        
        # Convert to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # Generate pledge ID
        pledge_id = str(uuid.uuid4())
        
        # Save to DynamoDB
        save_pledge_to_dynamodb(employee_id, employee_name, department, designation, pledge_id)
        
        # Upload to S3
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        s3_key = f"certificates/{employee_id}_{timestamp}.pdf"
        
        try:
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=pdf_bytes,
                ContentType='application/pdf'
            )
            print(f"✓ Certificate uploaded to S3: {s3_key}")
        except Exception as e:
            print(f"⚠ S3 upload failed (non-critical): {str(e)}")
        
        print(f"✓ Pledge processed successfully for {employee_id}")
        
        # Return success - NO CORS headers (Function URL handles it)
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},  # Only Content-Type
            'body': json.dumps({
                'success': True,
                'message': 'Pledge submitted successfully',
                'employee_name': employee_name,
                'employee_id': employee_id,
                'department': department,
                'designation': designation,
                'pledge_id': pledge_id,
                'pdf_base64': pdf_base64,
                'certificate_size_kb': round(len(pdf_bytes) / 1024, 2)
            })
        }
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'success': False, 'message': f'Internal server error: {str(e)}'})
        }