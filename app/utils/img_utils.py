import base64
import mimetypes


def image_to_base64(image_path) -> str:
    mime_type, _ = mimetypes.guess_type(image_path)
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded_string
        # dataurl = rf"data:{mime_type};base64,{encoded_string}"
        # return dataurl
