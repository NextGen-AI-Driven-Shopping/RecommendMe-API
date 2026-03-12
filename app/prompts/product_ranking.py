import json
from typing import Any, Dict, List

# Prompt template used to ask GPT-4o for product ranking.
# The template expects two formatted values:
#  - user_context: information about the current browsing session or query
#  - products: a JSON-formatted list of product dictionaries
PROMPT_TEMPLATE = (
    """
You are a highly knowledgeable ecommerce expert.  Your job is to
choose the **best three** products from the list below for the
current user, give a concise reasoning for each selection, and write
an "expert_tip" that helps the shopper make a smarter purchase.

User context: {user_context}

Input products (JSON array):
{products}

Respond with a JSON array containing exactly three objects.  Each
object must have the following fields:
  - title      (string)  : the product title as given in the input
  - price      (number)  : the product price
  - rating     (number)  : average star rating
  - reason     (string)  : why this product was selected for this user
  - expert_tip (string)  : bonus advice or a note that demonstrates
                           domain expertise

Make sure the explanations refer to the user context rather than
sounding generic.  Do not wrap the array in any prose or markdown.
"""
)


def build_prompt(
    products: List[Dict[str, Any]],
    user_context: str = "",
) -> str:
    """Return the full prompt text given raw product information.

    The ``products`` argument is normally the raw output returned from
    a search service (SerpAPI, etc).  Only fields that appear in the
    template are guaranteed; other keys are ignored.

    Example ``products`` entry:
        {"title": "Widget 3000", "price": 19.99, "rating": 4.5}
    """

    # sanitize/serialize product list
    formatted = json.dumps(products, indent=2, ensure_ascii=False)
    return PROMPT_TEMPLATE.format(user_context=user_context, products=formatted)


# simple helper to parse the model output back into python objects

def parse_response(output: str) -> List[Dict[str, Any]]:
    """Attempt to deserialize the JSON returned by the model.

    Raises :class:`ValueError` if parsing fails.
    """

    # The model is instructed to return raw JSON, but users sometimes
    # get stray backticks or trailing punctuation, so we try to locate
    # the first bracket and decode from there.
    start = output.find("[")
    if start == -1:
        raise ValueError("could not find JSON array in model output")
    try:
        return json.loads(output[start:])
    except json.JSONDecodeError as exc:
        raise ValueError("failed to decode model output") from exc
