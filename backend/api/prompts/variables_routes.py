import os

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/variables-reference")
def get_variables_reference(lang: str = "en") -> dict:
    """
    Get the prompt variables reference document (Markdown format).
    Used by frontend to display the strategy parameter guide.

    Args:
        lang: Language code ("en" for English, "zh" for Chinese)
    """
    # Select document based on language
    if lang == "zh":
        filename = "PROMPT_VARIABLES_REFERENCE_ZH.md"
    else:
        filename = "PROMPT_VARIABLES_REFERENCE.md"

    doc_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config",
        filename
    )

    try:
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Reference document not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read document: {str(e)}")
