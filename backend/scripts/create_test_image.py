"""
Create a simple test image with text for OCR testing.
"""
from PIL import Image, ImageDraw, ImageFont
import os

# Create a white image
width, height = 800, 400
image = Image.new('RGB', (width, height), color='white')
draw = ImageDraw.Draw(image)

# Add text
text = """
APPLICATION FOR DRIVING LICENSE

Name: Jane Smith
Date of Birth: 15/03/1995
Address: 123 Main Street, New York
License Type: Class B
Application Date: 18/08/2026
"""

try:
    # Try to use a better font if available
    font = ImageFont.truetype("arial.ttf", 24)
except:
    # Fall back to default font
    font = ImageFont.load_default()
    print("Using default font (text may be small)")

# Draw the text
draw.text((50, 50), text.strip(), fill='black', font=font)

# Save the image
output_path = "test_document.png"
image.save(output_path)
print(f"✅ Test image created: {output_path}")
print(f"📁 Full path: {os.path.abspath(output_path)}")
print("\n🧪 Now upload this image at: http://localhost:8000/docs")
print("   Use the POST /upload endpoint")
