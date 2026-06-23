import fitz
from paddleocr import PaddleOCR
from PIL import Image
import io
import tempfile
import os

ocr = PaddleOCR(use_angle_cls=True, lang='en')

def extract_text_from_image_file(image_path_or_file) -> str:
    temp_dir = tempfile.gettempdir()
    image_path = os.path.join(temp_dir, "temp_image.jpg")

    if hasattr(image_path_or_file, 'read'):
        img = Image.open(image_path_or_file)
        img.save(image_path)
    else:
        image_path = image_path_or_file

    result = ocr.predict(image_path)
    if not result:
        return ""

    texts = []
    for res in result:
        if 'rec_texts' in res:
            texts.extend(res['rec_texts'])

    return " ".join(texts).lower()


def extract_images_from_pdf(pdf_file) -> list:
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    images = []
    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            img_pil = Image.open(io.BytesIO(image_bytes))
            images.append(img_pil)
    doc.close()
    return images


def extract_text_from_pdf_images(pdf_file) -> str:
    images = extract_images_from_pdf(pdf_file)
    all_text = []
    temp_dir = tempfile.gettempdir()

    for i, img in enumerate(images):
        temp_path = os.path.join(temp_dir, f"pdf_img_{i}.jpg")
        img.save(temp_path)
        result = ocr.predict(temp_path)
        if result:
            for res in result:
                if 'rec_texts' in res:
                    all_text.extend(res['rec_texts'])

    return " ".join(all_text).lower()