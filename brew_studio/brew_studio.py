import json
import re
import socket
import io
import streamlit as st
from PIL import Image
from fellow_aiden import FellowAiden
from fellow_aiden.profile import CoffeeProfile, EspressoProfile
from openai import OpenAI

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

def call_gemini(client, contents, config=None):
    """Calls Gemini API with robust model fallback & retry for 503/429/404 errors."""
    import time
    candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
    last_exception = None
    
    for model_name in candidate_models:
        for attempt in range(2):  # Try twice per model with a brief delay
            try:
                if config:
                    return client.models.generate_content(model=model_name, contents=contents, config=config)
                else:
                    return client.models.generate_content(model=model_name, contents=contents)
            except Exception as e:
                last_exception = e
                err_str = str(e).upper()
                # Catch 503 UNAVAILABLE, 429 RESOURCE_EXHAUSTED, 404 NOT_FOUND, HIGH DEMAND
                if any(term in err_str for term in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "HIGH DEMAND", "404", "NOT_FOUND"]):
                    time.sleep(1.0)
                    continue
                raise e

    if last_exception:
        raise last_exception
    raise RuntimeError("All Gemini API models failed. Please try again.")

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def generate_qr_code_buf(url):
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=5, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None

def is_espresso_active():
    if not st.session_state.get("brewer_settings"):
        return False
    dev = st.session_state.brewer_settings.get("device_settings", {})
    name = str(dev.get("displayName", "")).lower()
    dev_type = str(dev.get("deviceType", "")).lower()
    sku = str(dev.get("sku", "")).lower()
    return ("solo" in dev_type or "espresso" in name or "1srw" in sku or "solo" in name)

SYSTEM = """
Assume the role of a master coffee brewer. You focus exclusively on the pour over method and specialty coffee only. You often work with single origin coffees, but you also experiment with blends. Your recipes are executed by a robot, not a human, so maximum precision can be achieved. Temperatures are all maintained and stable in all steps. Always lead with the recipe, and only include explanations below that text, NOT inline. Below are the components of a recipe. 

Core brew settings: These settings are static and must match for single and batch brew.
Title: An interesting and creative name based on the coffee details. 
Ratio: How much coffee per water. Values MUST be between 14 and 20 with 0.5 step increments.
Bloom ratio: Water to use in bloom stage. Values MUST be between 1 and 3 with 0.5 step increments.
Bloom time: How long the bloom phase should last. Values MUST be between 1 and 120 seconds.
Bloom temperature: Temperature of the water. Values MUST be between 50 and 99 celsius.

Pulse settings: These are independent and can vary for single and batch brews. 
Number of pulses: Steps in which water is poured over coffee. Values MUST be between 1 and 10.
Time between pulses: Time in between each pulse. Values MUST be between 5 and 60 seconds. This MUST be included even if a single pulse is performed. 
Pulse temperate. Independent temperature to use for a given pulse.  Values MUST be between 50 and 99 celsius.

Grinder Dial Settings Knowledge:
You are an expert on home coffee grinders. When given a coffee description or image, analyze roast density, process, and altitude, and determine the optimal grind size in microns (600-800µm for pour over).

Calculate the exact setting for the user's specific grinder model using these calibration curves:
- Fellow Ode Gen 2: Range 3.0 to 6.0 (e.g., 3.2 for light washed, 4.1 for medium, 5.1 for natural/dark).
- Fellow Ode Gen 1: Range 1.2 to 3.2.
- Baratza Encore / Virtuoso: Range 14 to 22 (e.g., 15 for light, 18 for medium).
- Comandante C40: Range 20 to 26 clicks.
- 1Zpresso K-Series: Range 6.0 to 7.5.
- Timemore C2/C3: Range 15 to 22 clicks.
- Niche Zero: Range 35 to 50 (e.g., 36 for light washed, 42 for medium, 48 for natural/dark).

Include a section titled "GRIND RECOMMENDATION" at the top of your explanation with the setting number and brief rationale.

Below is an example of a previous recipe you put together for a speciality coffee called "Fruit cake" where you tasted cinnamon sugar, baked apples, and blackberry compote.

Roast: Light - Medium
Process | Cinnamon co-ferment | Strawberry co-ferment | Washed
33% Esteban Zamora - Cinnamon Anaerobic (San Marcos, Tarrazu, Costa Rica)
33% Sebastián Ramirez - Red Fruits (Quindio, Colombia)
33% Gamatui - Washed (Kapchorwa, Mt. Elgon, Uganda)

CORE
Ratio: 16
Bloom ratio: 3
Bloom time: 60s
Bloom temp: 87.5°C

SINGLE SERVE
Pulse 1 temp: 95°C
Pulse 2 temp: 92.5°C
Time between pulses: 25s
Number of pulses: 2 

BATCH
Pulse 1 temp: 95°C
Pulse 2 temp: 92.5°C
Time between pulses: 25s
Number of pulses: 2 

Here's another example. This coffee is a bold and intense cup composed of a smooth blend of Burundian and Latin American coffees with notes of mulled wine, baker's chocolate, blood orange, and a delicious blast of fudge.

Roast: Light - Medium
Process: Natural and Washed
Region: Burundi, Honduras and Peru
CORE
Ratio: 16
Bloom ratio: 2.5  
Bloom time: 30s
Bloom temp: 93.5°C 

SINGLE SERVE
Pulse 1 temp: 92°C
Pulse 2 temp: 92°C
Pulse 3 temp: 90.5°C 
Time between pulses: 20s
Number of pulses: 3 

BATCH
Pulse temp: 92°C 
Number of pulses: 1
"""

REFORMAT_SYSTEM = """
Assume the role of a data engineer. You need to parse coffee recipes and their explanations so the data can be structured. Below are the important components of the recipe.

Core brew settings: These settings are static and must match for single and batch brew.
Title: An interesting and creative name based on the coffee details. 
Ratio: How much coffee per water. Values range from 1:14 to 1:20 with 0.5 steps.
Bloom ratio: Water to use in bloom stage. Values range from 1 to 3 with 0.5 steps.
Bloom time: How long the bloom phase should last. Values range from 1 to 120 seconds.
Bloom temperature: Temperature of the water. Values range from 50 celsius to 99 celsius.

Pulse settings: These are independent and can vary for single and batch brews. 
Number of pulses: Steps in which water is poured over coffee. Values range from 1 to 10.
Time between pulses: Time in between each pulse. Values range from 5 to 60 seconds. This must be included even if a single pulse is performed. 
Pulse temperate. Independent temperature to use for a given pulse.  Values range from 50 celsius to 99 celsius. 
"""

def connect_to_coffee_brewer(email, password):
    """Function returning a list of profile dicts."""
    email = email.strip()
    password = password.strip()

    if 'aiden' not in st.session_state:
        try:
            local = FellowAiden(email, password)
        except Exception as e:
            if "incorrect" in str(e):
                return False
            raise e
        st.session_state['aiden'] = local

    obj = {
        'device_settings': {
            'name': st.session_state['aiden'].get_display_name(),
        },
        'profiles': [
            {
                **p,
                **{"description": p.get("description", "")}
            }
            for p in st.session_state['aiden'].get_profiles()
        ]
    }
    return obj

def save_profile_to_coffee_machine(profile_name, updated_profile):
    st.success(f"Profile '{profile_name}' saved.")
    if 'description' in updated_profile:
        updated_profile.pop('description', None)
    updated_profile['profileType'] = 0
    
    try:
        existing_profile = st.session_state['aiden'].get_profile_by_title(profile_name)
        if existing_profile:
            profile_id = existing_profile['id']
            st.session_state['aiden'].update_profile(profile_id, updated_profile)
        else:
            st.session_state['aiden'].create_profile(updated_profile)
    except Exception as e:
        st.warning(f"Failed to save profile: {e}")

def parse_brewlink(link):
    """Returns a dict with all profile fields parsed from the link."""
    parsed = st.session_state['aiden'].parse_brewlink_url(link)
    if 'description' not in parsed:
        parsed['description'] = ""
    return parsed

GEMINI_GEM_PROMPT = """Assume the role of a master coffee brewer and data engineer for the Fellow Aiden pour-over machine.
You focus exclusively on pour-over specialty coffee.

When given a coffee description or roaster notes, output TWO sections:

1. **RECIPE & RATIONALE**: A detailed explanation of your pour over strategy, brew ratio, bloom, and temperature pulse decisions.
2. **BREW PROFILE JSON**: At the end of your response, output a markdown ```json block conforming EXACTLY to this schema so it can be loaded directly into Fellow Brew Studio:

```json
{
  "profileType": 0,
  "title": "<Creative title max 50 chars>",
  "ratio": 16,
  "bloomEnabled": true,
  "bloomRatio": 2,
  "bloomDuration": 30,
  "bloomTemperature": 96,
  "ssPulsesEnabled": true,
  "ssPulsesNumber": 3,
  "ssPulsesInterval": 23,
  "ssPulseTemperatures": [96, 97, 98],
  "batchPulsesEnabled": true,
  "batchPulsesNumber": 2,
  "batchPulsesInterval": 30,
  "batchPulseTemperatures": [96, 97]
}
```

Constraints:
- Ratio: between 14 and 20 in 0.5 step increments.
- Bloom ratio: between 1 and 3 in 0.5 step increments.
- Bloom time: 1 to 120 seconds.
- Bloom & Pulse temperatures: 50 to 99 °C.
- Pulse count: 1 to 10. Time between pulses: 5 to 60 seconds.
"""

def parse_manual_gem_recipe(raw_text):
    """
    Parses a JSON block or text payload generated by a Gemini Gem or manual input into a CoffeeProfile dict.
    """
    text = raw_text.strip()
    json_str = None

    # Try finding JSON block enclosed in ```json ... ```
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    elif text.startswith('{') and text.endswith('}'):
        json_str = text
    else:
        # Try extracting any { ... } block
        curly_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if curly_match:
            json_str = curly_match.group(1)

    if not json_str:
        raise ValueError("No valid JSON block found. Please ensure your Gem output includes a ```json ... ``` codeblock.")

    data = json.loads(json_str)
    description = data.pop('description', text)
    validated = CoffeeProfile.model_validate(data)
    recipe = validated.model_dump()
    recipe['description'] = description
    return recipe

def call_gemini(client, contents, config=None):
    """Calls Gemini API with robust model fallback & retry for 503/429/404 errors."""
    import time
    candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
    last_exception = None
    
    for model_name in candidate_models:
        for attempt in range(2):  # Try twice per model with a brief delay
            try:
                if config:
                    res = client.models.generate_content(model=model_name, contents=contents, config=config)
                else:
                    res = client.models.generate_content(model=model_name, contents=contents)
                return res, model_name
            except Exception as e:
                last_exception = e
                err_str = str(e).upper()
                # Catch 503 UNAVAILABLE, 429 RESOURCE_EXHAUSTED, 404 NOT_FOUND, HIGH DEMAND
                if any(term in err_str for term in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "HIGH DEMAND", "404", "NOT_FOUND"]):
                    time.sleep(1.0)
                    continue
                raise e

    if last_exception:
        raise last_exception
    raise RuntimeError("All Gemini API models failed. Please try again.")


def generate_gemini_recipe_and_explanation(USER, gemini_api_key):
    """Generates recipe and explanation using Google Gemini API."""
    if not HAS_GENAI:
        raise ImportError("google-genai package is not installed.")

    client = genai.Client(api_key=gemini_api_key.strip())
    selected_grinder = st.session_state.get("selected_grinder", "Fellow Ode (Gen 2)")
    guidance = f"Suggest a recipe for the following coffee. User's Grinder Model: {selected_grinder}. Provide the exact dial setting number for this grinder and explanations below the recipe.\n"
    prompt_text = SYSTEM + "\n\n" + guidance + USER

    # Step 1: Generate freeform explanation
    response, used_model = call_gemini(client, contents=prompt_text)
    model_explanation = response.text

    # Step 2: Extract structured CoffeeProfile JSON
    reformat_prompt = f"{REFORMAT_SYSTEM}\n\nRecipe text to parse:\n{model_explanation}"
    extract_response, _ = call_gemini(
        client,
        contents=reformat_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CoffeeProfile,
        )
    )

    recipe_dict = json.loads(extract_response.text)
    validated = CoffeeProfile.model_validate(recipe_dict)
    recipe = validated.model_dump()
    recipe['description'] = model_explanation
    recipe['model_used'] = used_model
    return recipe


def generate_gemini_vision_recipe_and_explanation(pil_image, user_notes, gemini_api_key):
    """Analyzes a coffee bag photo using Gemini Vision and generates a recipe."""
    if not HAS_GENAI:
        raise ImportError("google-genai package is not installed.")

    client = genai.Client(api_key=gemini_api_key.strip())
    selected_grinder = st.session_state.get("selected_grinder", "Fellow Ode (Gen 2)")
    
    prompt = (
        SYSTEM + "\n\n"
        "You are presented with an image of a coffee bag label (and optional user notes).\n"
        "1. Carefully inspect the label and read all text: roaster name, coffee title, origin/country/region, "
        "processing method (washed, natural, anaerobic, honey, etc.), roast level, and tasting notes.\n"
        "2. Based on these extracted details, design an optimal specialty pour-over recipe for the Fellow Aiden.\n"
        f"3. User's Grinder Model: {selected_grinder}. Provide the exact dial setting number for this grinder.\n"
        "4. Lead with your GRIND RECOMMENDATION and recipe rationale, followed by the recipe components.\n"
    )
    if user_notes:
        prompt += f"\nUser Additional Notes: {user_notes}\n"

    response, used_model = call_gemini(client, contents=[pil_image, prompt])
    model_explanation = response.text

    reformat_prompt = f"{REFORMAT_SYSTEM}\n\nRecipe text to parse:\n{model_explanation}"
    extract_response, _ = call_gemini(
        client,
        contents=reformat_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CoffeeProfile,
        )
    )

    recipe_dict = json.loads(extract_response.text)
    validated = CoffeeProfile.model_validate(recipe_dict)
    recipe = validated.model_dump()
    recipe['description'] = model_explanation
    recipe['model_used'] = used_model
    return recipe


ESPRESSO_SYSTEM = """
Assume the role of a master espresso barista and extraction scientist.
You create precise espresso extraction profiles for home espresso machines like the Fellow Series 1 Solo.

When provided with a coffee description or image, analyze roast level, processing method (washed, natural, anaerobic, honey, co-ferment), elevation, and tasting notes.

Determine:
1. Title: Creative espresso recipe title.
2. Dose in grams: 14.0g to 22.0g.
3. Yield in grams: 28.0g to 60.0g.
4. Ratio: Target extraction ratio (e.g. 1:2.0, 1:2.2, 1:2.5).
5. Water Temperature: 88.0°C to 98.0°C.
6. Pre-Infusion Seconds: 0 to 15 seconds.
7. Pre-Infusion Pressure: 1.0 to 4.0 bar.
8. Peak Pressure: 6.0 to 9.0 bar.
9. Target Shot Time: 25 to 40 seconds.
10. Grind Recommendation: Exact dial setting for the user's espresso grinder.

Always lead with your espresso extraction rationale and tasting notes.
"""

def generate_gemini_espresso_recipe_and_explanation(USER, gemini_api_key):
    """Generates espresso extraction profile using Google Gemini API."""
    if not HAS_GENAI:
        raise ImportError("google-genai package is not installed.")

    client = genai.Client(api_key=gemini_api_key.strip())
    selected_grinder = st.session_state.get("selected_grinder", "Fellow Ode (Gen 2)")
    prompt_text = (
        ESPRESSO_SYSTEM + "\n\n"
        f"Coffee Description: {USER}\n"
        f"User's Grinder Model: {selected_grinder}\n"
    )

    response, used_model = call_gemini(client, contents=prompt_text)
    model_explanation = response.text

    reformat_prompt = f"Parse the following espresso recipe explanation into JSON.\n\n{model_explanation}"
    extract_response, _ = call_gemini(
        client,
        contents=reformat_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EspressoProfile,
        )
    )

    recipe_dict = json.loads(extract_response.text)
    validated = EspressoProfile.model_validate(recipe_dict)
    recipe = validated.model_dump()
    recipe['description'] = model_explanation
    recipe['model_used'] = used_model
    return recipe

def generate_gemini_vision_espresso_recipe_and_explanation(pil_image, user_notes, gemini_api_key):
    """Analyzes a coffee bag photo using Gemini Vision and generates an espresso profile."""
    if not HAS_GENAI:
        raise ImportError("google-genai package is not installed.")

    client = genai.Client(api_key=gemini_api_key.strip())
    selected_grinder = st.session_state.get("selected_grinder", "Fellow Ode (Gen 2)")
    
    prompt = (
        ESPRESSO_SYSTEM + "\n\n"
        "Analyze this coffee bag label image. Extract roaster, coffee name, process, roast level, and tasting notes.\n"
        f"User's Grinder Model: {selected_grinder}.\n"
    )
    if user_notes:
        prompt += f"User Notes: {user_notes}\n"

    response, used_model = call_gemini(client, contents=[pil_image, prompt])
    model_explanation = response.text

    reformat_prompt = f"Parse the following espresso recipe explanation into JSON.\n\n{model_explanation}"
    extract_response, _ = call_gemini(
        client,
        contents=reformat_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EspressoProfile,
        )
    )

    recipe_dict = json.loads(extract_response.text)
    validated = EspressoProfile.model_validate(recipe_dict)
    recipe = validated.model_dump()
    recipe['description'] = model_explanation
    recipe['model_used'] = used_model
    return recipe


def extract_recipe_from_description(model_explanation):
    """Extracts the recipe from the description using OpenAI."""
    try:
        completion = st.session_state['oai'].beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": REFORMAT_SYSTEM},
                {"role": "user", "content": model_explanation},
            ],
            response_format=CoffeeProfile,
        )
        model_recipe = completion.choices[0].message.parsed
    except Exception as e:
        print("Failed to extract recipe from description:", e)
        return False
    
    return model_recipe


def generate_ai_recipe_and_explanation(USER):
    selected_grinder = st.session_state.get("selected_grinder", "Fellow Ode (Gen 2)")
    guidance = f"Suggest a recipe for the following coffee. User's Grinder Model: {selected_grinder}. Provide the exact dial setting number for this grinder and explanations below the recipe.\n"
    USER = ' '.join([guidance, USER])
    completion = st.session_state['oai'].chat.completions.create(
        model="o1-preview",
        messages=[
            {"role": "user", "content": SYSTEM + USER},
        ]
    )
    model_explanation = completion.choices[0].message.content
    print(model_explanation)

    while True:
        model_recipe = extract_recipe_from_description(model_explanation)
        if model_recipe:
            break

    recipe = model_recipe.model_dump()
    recipe['description'] = model_explanation
    return recipe


def get_share_link(profile_input):
    """Generates an authentic Fellow brew.link for a profile dict or title."""
    if not st.session_state.get('aiden'):
        raise ValueError("Not connected to Fellow machine.")
    
    aiden = st.session_state['aiden']
    
    if isinstance(profile_input, dict):
        p_data = profile_input
    else:
        found = aiden.get_profile_by_title(str(profile_input))
        p_data = found if found else {"title": str(profile_input)}

    profile_id = p_data.get("id")

    # If profile has no server ID, save it to cloud first to receive a server ID
    if not profile_id:
        saved_profile = aiden.create_profile(p_data)
        if isinstance(saved_profile, dict) and "id" in saved_profile:
            profile_id = saved_profile["id"]

    if profile_id:
        try:
            return aiden.generate_share_link(profile_id)
        except Exception:
            return f"https://brew.link/p/{profile_id}"

    raise ValueError(f"Could not generate share link for profile '{p_data.get('title')}'")

# ------------------------------------------------------------------------------
# Streamlit Setup
# ------------------------------------------------------------------------------
st.set_page_config(layout="wide")

st.markdown(
    """
    <style>
    hr { 
        margin: 0em;
        border-width: 2px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

if "brewer_settings" not in st.session_state:
    st.session_state.brewer_settings = None

if "new_profile" not in st.session_state:
    st.session_state.new_profile = None

if "selected_profile_index" not in st.session_state:
    st.session_state.selected_profile_index = None

# ------------------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------------------
with st.sidebar:
    import os
    default_email = os.environ.get("FELLOW_EMAIL", "")
    if not default_email and hasattr(st, "secrets") and "FELLOW_EMAIL" in st.secrets:
        default_email = st.secrets["FELLOW_EMAIL"]

    default_password = os.environ.get("FELLOW_PASSWORD", "")
    if not default_password and hasattr(st, "secrets") and "FELLOW_PASSWORD" in st.secrets:
        default_password = st.secrets["FELLOW_PASSWORD"]

    st.header("Fellow Email Address")
    email = st.text_input(" ", value=st.session_state.get("email", default_email), placeholder="Enter your email", 
                          key="email", label_visibility="collapsed")

    st.header("Fellow Password")
    password = st.text_input(" ", value=st.session_state.get("password", default_password), placeholder="Enter your password", 
                             type="password", key="password", label_visibility="collapsed")

    # Auto connect if secrets are provided and not already connected
    if not st.session_state.brewer_settings and default_email and default_password and "auto_connected" not in st.session_state:
        st.session_state["auto_connected"] = True
        result = connect_to_coffee_brewer(default_email, default_password)
        if result:
            st.session_state.brewer_settings = result

    # Connect button
    if st.button("Connect"):
        if email and password:
            result = connect_to_coffee_brewer(email, password)
            if not result:
                st.warning("Incorrect email or password.")
            st.session_state.brewer_settings = result
        else:
            st.warning("Please enter email and password first.")

    st.markdown("---")

    # Grinder Selection
    GRINDER_MODELS = [
        "Fellow Ode (Gen 2)",
        "Fellow Ode (Gen 1)",
        "Baratza Encore / Virtuoso",
        "Comandante C40",
        "1Zpresso K-Series",
        "Timemore C2/C3",
        "Niche Zero",
        "Generic / Microns"
    ]

    default_grinder = os.environ.get("PREFERRED_GRINDER", "Fellow Ode (Gen 2)")
    if hasattr(st, "secrets") and "PREFERRED_GRINDER" in st.secrets:
        default_grinder = st.secrets["PREFERRED_GRINDER"]

    selected_grinder = st.selectbox(
        "⚙️ Your Coffee Grinder",
        GRINDER_MODELS,
        index=GRINDER_MODELS.index(default_grinder) if default_grinder in GRINDER_MODELS else 0,
        key="selected_grinder"
    )

    st.markdown("---")

    # Mobile Phone Pairing & QR Code helper
    local_ip = get_local_ip()
    mobile_url = f"http://{local_ip}:8501"
    with st.expander("📱 Mobile Phone Pairing & QR Code"):
        st.markdown(f"**Local Network URL**:\n`{mobile_url}`")
        st.markdown("Connect your phone to the same Wi-Fi network and scan the QR code below:")
        qr_buf = generate_qr_code_buf(mobile_url)
        if qr_buf:
            st.image(qr_buf, caption="Scan with Phone Camera", width=180)

    # If connected, show device info and profile management
    if st.session_state.brewer_settings:
        all_devices = st.session_state['aiden'].get_devices()
        if all_devices:
            device_options = [f"{d.get('displayName', 'Device')} (ID: {d.get('id', '')})" for d in all_devices]
            current_idx = st.session_state.get("current_device_idx", 0)
            if current_idx >= len(device_options):
                current_idx = 0

            selected_dev = st.selectbox(
                "🔌 Active Device",
                device_options,
                index=current_idx,
                key="active_device_selector"
            )
            selected_idx = device_options.index(selected_dev)
            if st.session_state.get("current_device_idx") != selected_idx:
                st.session_state["current_device_idx"] = selected_idx
                st.session_state.selected_profile_index = None
                st.session_state.selected_profile_choice = "— None —"
                st.session_state.new_profile = None
                st.session_state['aiden'].select_device(selected_idx)
                st.session_state.brewer_settings = {
                    "device_settings": st.session_state['aiden'].get_device_config(),
                    "profiles": st.session_state['aiden'].get_profiles(),
                    "schedules": st.session_state['aiden'].get_schedules()
                }
                st.rerun()

        st.markdown("**New Profile from Brew Link**")

        brew_link = st.text_input(
            "Brew Link",
            placeholder="Paste brew link here...",
            key="brew_link"
        )
        
        # Create profile from brew link
        if st.button("Create Profile from Brew Link"):
            # 1. Parse the new data
            new_profile_data = parse_brewlink(brew_link)
            
            # 2. Clear out old "new_*" keys
            for key in list(st.session_state.keys()):
                if key.startswith("new_"):
                    del st.session_state[key]
            
            # 3. Set the brand-new profile
            st.session_state.new_profile = new_profile_data
            
            # 4. Clear out existing profile selection
            st.session_state.selected_profile_index = None
            st.session_state.selected_profile_choice = "— None —"

        st.markdown("---")

        # ---- AI BARISTA SECTION ----
        st.markdown("### AI Barista")
        
        ai_provider = st.selectbox(
            "AI Provider",
            ["Google Gemini (Gem / No API Key)", "Google Gemini (API Key)", "OpenAI (ChatGPT)"],
            key="ai_provider"
        )

        if ai_provider == "Google Gemini (Gem / No API Key)":
            with st.expander("📋 Gemini Gem Setup Instructions"):
                st.markdown("1. Open [gemini.google.com](https://gemini.google.com) and click **Gems -> New Gem**.")
                st.markdown("2. Name it **Fellow Aiden Barista**.")
                st.markdown("3. Copy & paste the prompt instructions below into your Gem System Instructions:")
                st.code(GEMINI_GEM_PROMPT, language="markdown")
                st.markdown("4. Chat with your Gem about any coffee! Copy the output from Gemini and paste it into the box below.")

            gem_paste_input = st.text_area(
                "Paste Gem Output or JSON Recipe:",
                placeholder="Paste the output or JSON generated by your Gemini Gem here...",
                key="gem_paste_input",
                height=150
            )

            if st.button("Load Recipe from Gem Output", key="gem_parse_button"):
                if gem_paste_input.strip():
                    try:
                        new_profile_data = parse_manual_gem_recipe(gem_paste_input)
                        for key in list(st.session_state.keys()):
                            if key.startswith("new_"):
                                del st.session_state[key]
                        st.session_state.new_profile = new_profile_data
                        st.session_state.selected_profile_index = None
                        st.session_state.selected_profile_choice = "— None —"
                        st.success("Gem profile loaded successfully!")
                    except Exception as e:
                        st.warning(f"Failed to parse Gem recipe: {e}")
                else:
                    st.warning("Please paste Gem output or JSON first.")

        elif ai_provider == "Google Gemini (API Key)":
            import os
            default_gemini_key = os.environ.get("GEMINI_API_KEY", "")
            if not default_gemini_key and hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
                default_gemini_key = st.secrets["GEMINI_API_KEY"]

            gemini_api_key = st.text_input(
                "Google Gemini API Key",
                value=st.session_state.get("gemini_api_key", default_gemini_key),
                placeholder="Enter Gemini API Key (from AI Studio)",
                type="password",
                key="gemini_api_key"
            )

            gemini_mode_tab1, gemini_mode_tab2 = st.tabs(["📝 Text Description", "📷 Coffee Bag Photo"])

            with gemini_mode_tab1:
                user_coffee_request = st.text_area(
                    "Describe your coffee:",
                    placeholder="Light roasted blend of washed (Sidama, Ethiopia) and gesha (Santa Barbara, Honduras) coffees",
                    key="gemini_coffee_input"
                )
                btn_label = "Generate Gemini Espresso Profile" if is_espresso_active() else "Generate Gemini AI Profile"
                if st.button(btn_label, key="gemini_generate_button"):
                    if gemini_api_key.strip():
                        if user_coffee_request.strip():
                            try:
                                with st.spinner("Generating recipe with Gemini..."):
                                    if is_espresso_active():
                                        new_profile_data = generate_gemini_espresso_recipe_and_explanation(user_coffee_request, gemini_api_key)
                                    else:
                                        new_profile_data = generate_gemini_recipe_and_explanation(user_coffee_request, gemini_api_key)
                                for key in list(st.session_state.keys()):
                                    if key.startswith("new_"):
                                        del st.session_state[key]
                                st.session_state.new_profile = new_profile_data
                                st.session_state.selected_profile_index = None
                                st.session_state.selected_profile_choice = "— None —"
                                st.success("Gemini profile generated!")
                            except Exception as e:
                                st.warning(f"Failed to generate Gemini AI recipe: {e}")
                        else:
                            st.warning("Please enter a coffee description first.")
                    else:
                        st.warning("Please enter a Gemini API key first.")

            with gemini_mode_tab2:
                img_source_tab1, img_source_tab2 = st.tabs(["📁 File Upload", "📷 Camera Snap"])
                uploaded_img_file = None

                with img_source_tab1:
                    uploaded_file = st.file_uploader(
                        "Upload Coffee Bag Photo",
                        type=["jpg", "jpeg", "png", "webp"],
                        key="vision_file_uploader"
                    )
                    if uploaded_file:
                        uploaded_img_file = uploaded_file

                with img_source_tab2:
                    camera_file = st.camera_input("Snap Coffee Bag Photo", key="vision_camera_input")
                    if camera_file:
                        uploaded_img_file = camera_file

                if uploaded_img_file:
                    pil_img = Image.open(uploaded_img_file)
                    st.image(pil_img, caption="Coffee Bag Preview", use_container_width=True)

                vision_notes = st.text_input(
                    "Extra Notes (Optional):",
                    placeholder="e.g. Ground with Ode Gen 2 or Niche Zero",
                    key="vision_extra_notes"
                )

                if st.button("Scan Photo & Generate Profile", key="gemini_vision_generate_button"):
                    if gemini_api_key.strip():
                        if uploaded_img_file:
                            try:
                                pil_img = Image.open(uploaded_img_file)
                                with st.spinner("Scanning coffee bag with Gemini Vision..."):
                                    if is_espresso_active():
                                        new_profile_data = generate_gemini_vision_espresso_recipe_and_explanation(
                                            pil_img, vision_notes, gemini_api_key
                                        )
                                    else:
                                        new_profile_data = generate_gemini_vision_recipe_and_explanation(
                                            pil_img, vision_notes, gemini_api_key
                                        )
                                for key in list(st.session_state.keys()):
                                    if key.startswith("new_"):
                                        del st.session_state[key]
                                st.session_state.new_profile = new_profile_data
                                st.session_state.selected_profile_index = None
                                st.session_state.selected_profile_choice = "— None —"
                                st.success("Coffee bag scanned and profile generated!")
                            except Exception as e:
                                st.warning(f"Failed to scan coffee bag photo: {e}")
                        else:
                            st.warning("Please upload or snap a photo of your coffee bag first.")
                    else:
                        st.warning("Please enter a Gemini API key first.")

        elif ai_provider == "OpenAI (ChatGPT)":
            st.markdown("#### OpenAI API Key")
            openai_api_key = st.text_input(" ", placeholder="Enter your OpenAI API Key", 
                                        type="password", key="openai_api_key", label_visibility="collapsed")
            user_coffee_request = st.text_area(
                "Describe your coffee:",
                placeholder="Light roasted blend of washed (Sidama, Ethiopia) and gesha (Santa Barbara, Honduras) coffees",
                key="ai_barista_input"
            )

            openai_api_key = openai_api_key.strip()
            if st.button("Generate AI Profile", key="ai_barista_button"):
                if openai_api_key.strip():
                    st.session_state['oai'] = OpenAI(api_key=openai_api_key)
                    if user_coffee_request.strip():

                        try:
                            new_profile_data = generate_ai_recipe_and_explanation(user_coffee_request)
                        except Exception as e:
                            st.warning(f"Failed to generate AI recipe: {e}")
                            new_profile_data = None
                        
                        # 2. Clear out old "new_*" keys
                        for key in list(st.session_state.keys()):
                            if key.startswith("new_"):
                                del st.session_state[key]
                        
                        # 3. Set the brand-new profile
                        st.session_state.new_profile = new_profile_data
                        
                        # 4. Clear out existing profile selection
                        st.session_state.selected_profile_index = None
                        st.session_state.selected_profile_choice = "— None —"

                    else:
                        st.warning("Please enter a description first.")
                else:
                    st.warning("Please enter an OpenAI key first.")

        st.markdown("---")

        # ---- Existing Profiles ----
        st.markdown("**Existing Profiles**")
        profiles = st.session_state.brewer_settings.get("profiles", [])
        titles = []
        if isinstance(profiles, list):
            for p in profiles:
                if isinstance(p, dict):
                    titles.append(p.get("title", p.get("name", p.get("id", "Untitled Profile"))))
                elif isinstance(p, str):
                    titles.append(p)
                else:
                    titles.append(str(p))
        elif isinstance(profiles, dict):
            titles = list(profiles.keys())

        choice = st.selectbox(
            "Select a Profile", 
            ["— None —"] + titles, 
            key="selected_profile_choice"
        )
        if choice != "— None —":
            st.session_state.selected_profile_index = titles.index(choice)
            st.session_state.new_profile = None
        else:
            st.session_state.selected_profile_index = None

        st.markdown("---")     
        device_info = st.session_state.brewer_settings["device_settings"]
        st.markdown("**Connected Brewer Settings**")
        for k, v in device_info.items():
            st.write(f"**{k.replace('_', ' ').title()}**: {v}")
        if st.button("Dump Config"):
            st.write(st.session_state['aiden'].get_device_config())



# ------------------------------------------------------------------------------
# Helper: Profile Editor
# ------------------------------------------------------------------------------
def render_profile_editor(profile_dict, profile_key="existing"):
    """
    Renders the same set of sliders/checkboxes used for editing a profile,
    plus a text area for 'description'.
    """
    def ss_key(k):
        return f"{profile_key}_{k}"

    st.write("### Editing Profile")
    model_used = profile_dict.get("model_used")
    if model_used:
        st.caption(f"🤖 **Generated by AI Model**: `{model_used}`")

    # Display Grind Size Recommendation Banner if present
    description_text = profile_dict.get("description", "")
    if "GRIND RECOMMENDATION" in description_text.upper() or "SETTING" in description_text.upper():
        current_grinder = st.session_state.get("selected_grinder", "Your Grinder")
        st.info(f"⚙️ **Grinder Setting for {current_grinder}**\n\nSee full rationale in Description below.")

    # Title
    st.session_state[ss_key("title")] = st.text_input(
        "Profile Title",
        value=profile_dict["title"],
        key=ss_key("title_input")
    )

    # Description (AI Explanation or user text)
    st.session_state[ss_key("description")] = st.text_area(
        "Description (auto-filled by AI Barista or manually edited):",
        value=profile_dict.get("description", ""),   # default to "" if missing
        key=ss_key("description_input"),
        height=100
    )

    # Save button
    if st.button("Save", key=ss_key("save_button")):
        updated_profile = {
            "profileType": profile_dict.get("profileType", "custom"),  
            "title": st.session_state[ss_key("title_input")],
            "description": st.session_state.get(ss_key("description_input"), profile_dict.get("description", "")),
            "ratio": st.session_state.get(ss_key("ratio"), profile_dict.get("ratio", 16.0)),
            "bloomRatio": st.session_state.get(ss_key("bloomRatio"), profile_dict.get("bloomRatio", 2.0)),
            "bloomDuration": st.session_state.get(ss_key("bloomDuration"), profile_dict.get("bloomDuration", 30)),
            "bloomTemperature": st.session_state.get(ss_key("bloomTemperature"), profile_dict.get("bloomTemperature", 93.0)),
            "bloomEnabled": st.session_state.get(ss_key("bloomEnabled"), profile_dict.get("bloomEnabled", True)),
            "ssPulsesEnabled": st.session_state.get(ss_key("ssPulsesEnabled"), profile_dict.get("ssPulsesEnabled", False)),
            "ssPulsesNumber": st.session_state.get(ss_key("ssPulsesNumber"), profile_dict.get("ssPulsesNumber", 1)),
            "ssPulsesInterval": st.session_state.get(ss_key("ssPulsesInterval"), profile_dict.get("ssPulsesInterval", 10)),
            "ssPulseTemperatures": st.session_state.get(ss_key("ssPulseTemperatures"), profile_dict.get("ssPulseTemperatures", [93])),
            "batchPulsesEnabled": st.session_state.get(ss_key("batchPulsesEnabled"), profile_dict.get("batchPulsesEnabled", False)),
            "batchPulsesNumber": st.session_state.get(ss_key("batchPulsesNumber"), profile_dict.get("batchPulsesNumber", 1)),
            "batchPulsesInterval": st.session_state.get(ss_key("batchPulsesInterval"), profile_dict.get("batchPulsesInterval", 10)),
            "batchPulseTemperatures": st.session_state.get(ss_key("batchPulseTemperatures"), profile_dict.get("batchPulseTemperatures", [93])),
        }
        # print(updated_profile)
        save_profile_to_coffee_machine(updated_profile["title"], updated_profile)

        # Overwrite the original dict so we see changes right away
        for k, v in updated_profile.items():
            profile_dict[k] = v

    if st.button("🔗 Generate Brew Link & QR Code", key=ss_key("brewlink_button")):
        try:
            link = get_share_link(profile_dict)
            st.markdown(f"**Fellow Brew Link**: [{link}]({link})")
            qr_buf = generate_qr_code_buf(link)
            if qr_buf:
                st.image(qr_buf, caption="Scan with phone camera to import into Fellow App", width=200)
        except Exception as e:
            pid = profile_dict.get('id', 'custom')
            link = f"https://brew.link/p/{pid}"
            st.markdown(f"**Fellow Brew Link**: [{link}]({link})")
            qr_buf = generate_qr_code_buf(link)
            if qr_buf:
                st.image(qr_buf, caption="Scan with phone camera to import into Fellow App", width=200)

    # Bloom
    bloom_enabled = st.checkbox(
        "Enable Bloom?",
        value=profile_dict.get("bloomEnabled", True),
        key=ss_key("bloomEnabled")
    )
    ratio = st.slider(
        "Ratio",
        14.0, 20.0, step=0.5,
        value=float(profile_dict.get("ratio", 16.0)),
        key=ss_key("ratio")
    )

    if bloom_enabled:
        bloom_ratio = st.slider(
            "Bloom Ratio",
            1.0, 3.0, step=0.5,
            value=float(profile_dict.get("bloomRatio", 2.0)),
            key=ss_key("bloomRatio")
        )
        bloom_duration = st.slider(
            "Bloom Duration (seconds)",
            1, 120, step=1,
            value=profile_dict.get("bloomDuration", 30),
            key=ss_key("bloomDuration")
        )
        bloom_temp = st.slider(
            "Bloom Temperature (°C)",
            50.0, 99.0, step=0.5,
            value=float(profile_dict.get("bloomTemperature", 93.0)),
            key=ss_key("bloomTemperature")
        )
    else:
        st.write("Bloom is disabled.")

    st.markdown("---")
    # Single-Serve pulses
    ss_pulses_enabled = st.checkbox(
        "Enable Single-Serve Pulses?",
        value=profile_dict.get("ssPulsesEnabled", False),
        key=ss_key("ssPulsesEnabled")
    )
    ss_pulses_number = st.number_input(
        "Number of SS Pulses",
        min_value=1, max_value=10,
        value=profile_dict.get("ssPulsesNumber", 1),
        key=ss_key("ssPulsesNumber")
    )
    ss_pulses_interval = st.number_input(
        "Time between SS Pulses (sec)",
        min_value=1, max_value=60,
        value=profile_dict.get("ssPulsesInterval", 10),
        key=ss_key("ssPulsesInterval")
    )

    # Handle single-serve pulse temperatures
    if ss_key("ssPulseTemperatures") not in st.session_state:
        st.session_state[ss_key("ssPulseTemperatures")] = profile_dict.get("ssPulseTemperatures", [93])

    while len(st.session_state[ss_key("ssPulseTemperatures")]) < ss_pulses_number:
        st.session_state[ss_key("ssPulseTemperatures")].append(90)
    st.session_state[ss_key("ssPulseTemperatures")] = \
        st.session_state[ss_key("ssPulseTemperatures")][:ss_pulses_number]

    for i in range(ss_pulses_number):
        temp_key = f"{ss_key('ssTemp')}_{i}"
        st.session_state[ss_key("ssPulseTemperatures")][i] = st.slider(
            f"SS Pulse {i+1} Temperature (°C)",
            min_value=50.0, max_value=99.0, step=0.5,
            value=float(st.session_state[ss_key("ssPulseTemperatures")][i]),
            key=temp_key
        )

    st.markdown("---")
    # Batch pulses
    batch_pulses_enabled = st.checkbox(
        "Enable Batch Pulses?",
        value=profile_dict.get("batchPulsesEnabled", False),
        key=ss_key("batchPulsesEnabled")
    )
    batch_pulses_number = st.number_input(
        "Number of Batch Pulses",
        min_value=1, max_value=10,
        value=profile_dict.get("batchPulsesNumber", 1),
        key=ss_key("batchPulsesNumber")
    )
    batch_pulses_interval = st.number_input(
        "Time between Batch Pulses (sec)",
        min_value=1, max_value=60,
        value=profile_dict.get("batchPulsesInterval", 10),
        key=ss_key("batchPulsesInterval")
    )

    if ss_key("batchPulseTemperatures") not in st.session_state:
        st.session_state[ss_key("batchPulseTemperatures")] = profile_dict.get("batchPulseTemperatures", [93])

    while len(st.session_state[ss_key("batchPulseTemperatures")]) < batch_pulses_number:
        st.session_state[ss_key("batchPulseTemperatures")].append(90)
    st.session_state[ss_key("batchPulseTemperatures")] = \
        st.session_state[ss_key("batchPulseTemperatures")][:batch_pulses_number]

    for i in range(batch_pulses_number):
        temp_key = f"{ss_key('batchTemp')}_{i}"
        st.session_state[ss_key("batchPulseTemperatures")][i] = st.slider(
            f"Batch Pulse {i+1} Temperature (°C)",
            min_value=50.0, max_value=99.0, step=0.5,
            value=float(st.session_state[ss_key("batchPulseTemperatures")][i]),
            key=temp_key
        )

def render_espresso_profile_editor(profile_dict, profile_key="espresso"):
    """Renders the Espresso Profile Card, Machine Sync Button & Parameter Controls."""
    st.write("### ☕ Espresso Extraction Profile")
    
    title_val = profile_dict.get("title", "Untitled Espresso Profile")
    st.subheader(title_val)
    model_used = profile_dict.get("model_used")
    if model_used:
        st.caption(f"🤖 **Generated by AI Model**: `{model_used}`")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("☕ Dose", f"{profile_dict.get('dose_grams', 18.0)}g")
        st.metric("💧 Pre-Infusion", f"{profile_dict.get('pre_infusion_seconds', 6)}s @ {profile_dict.get('pre_infusion_pressure_bar', 3.0)} bar")
    with col2:
        st.metric("🥛 Yield", f"{profile_dict.get('yield_grams', 36.0)}g")
        st.metric("⚡ Peak Pressure", f"{profile_dict.get('peak_pressure_bar', 9.0)} bar")
    with col3:
        st.metric("⚖️ Ratio", f"{profile_dict.get('ratio', '1:2.0')}")
        st.metric("⏱️ Target Shot Time", f"{profile_dict.get('target_shot_time_seconds', 28)}s")
    with col4:
        st.metric("🌡️ Water Temp", f"{profile_dict.get('temperature_celsius', 93.0)}°C")
        st.metric("⚙️ Grinder Setting", f"{profile_dict.get('grind_recommendation', 'Medium-Fine')}")

    st.markdown("---")

    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        summary_text = (
            f"☕ {title_val}\n"
            f"• Dose: {profile_dict.get('dose_grams', 18.0)}g\n"
            f"• Yield: {profile_dict.get('yield_grams', 36.0)}g (Ratio: {profile_dict.get('ratio', '1:2.0')})\n"
            f"• Water Temp: {profile_dict.get('temperature_celsius', 93.0)}°C\n"
            f"• Pre-Infusion: {profile_dict.get('pre_infusion_seconds', 6)}s @ {profile_dict.get('pre_infusion_pressure_bar', 3.0)} bar\n"
            f"• Peak Pressure: {profile_dict.get('peak_pressure_bar', 9.0)} bar\n"
            f"• Target Shot Time: {profile_dict.get('target_shot_time_seconds', 28)}s\n"
            f"• Grinder Setting: {profile_dict.get('grind_recommendation', 'Fine')}"
        )
        if st.button("📋 Copy & Open Fellow App", key=f"{profile_key}_copy_app"):
            st.success("✅ Recipe copied to text view below!")
            st.markdown(f"📱 **[Tap to Open Fellow Mobile App](https://brew.link)**")
            st.code(summary_text, language="markdown")

    with col_btn2:
        if st.button("🔗 Generate QR Code", key=f"{profile_key}_brewlink"):
            try:
                link = get_share_link(profile_dict)
                st.markdown(f"**Fellow Series 1 Brew Link**: [{link}]({link})")
                qr_buf = generate_qr_code_buf(link)
                if qr_buf:
                    st.image(qr_buf, caption="Scan with phone camera to import into Fellow App", width=200)
            except Exception as e:
                summary_qr = (
                    f"Title: {title_val}\n"
                    f"Dose: {profile_dict.get('dose_grams', 18.0)}g\n"
                    f"Yield: {profile_dict.get('yield_grams', 36.0)}g\n"
                    f"Ratio: {profile_dict.get('ratio', '1:2.0')}\n"
                    f"Temp: {profile_dict.get('temperature_celsius', 93.0)}C\n"
                    f"Pre-Infusion: {profile_dict.get('pre_infusion_seconds', 6)}s @ {profile_dict.get('pre_infusion_pressure_bar', 3.0)} bar\n"
                    f"Peak Pressure: {profile_dict.get('peak_pressure_bar', 9.0)} bar\n"
                    f"Target Shot Time: {profile_dict.get('target_shot_time_seconds', 28)}s\n"
                    f"Grinder: {profile_dict.get('grind_recommendation', 'Fine')}"
                )
                qr_buf = generate_qr_code_buf(summary_qr)
                if qr_buf:
                    st.image(qr_buf, caption="Scan with phone camera to import specs", width=220)

    with col_btn3:
        if st.button("💾 Save Profile", key=f"{profile_key}_save"):
            try:
                res = st.session_state['aiden'].create_profile(profile_dict)
                if isinstance(res, dict) and res.get("id"):
                    st.success(f"Profile '{title_val}' saved to Fellow cloud over Wi-Fi!")
                else:
                    st.info(f"Espresso Profile '{title_val}' prepared. Tap 'Copy & Open Fellow App' to add it to your Series 1 over Bluetooth!")
            except Exception as e:
                st.info(f"Profile '{title_val}' prepared. Tap 'Copy & Open Fellow App' to add it to your Series 1 over Bluetooth!")

    st.markdown("---")
    st.markdown("#### 📖 Barista Rationale & Tasting Notes")
    st.write(profile_dict.get("description", "No description provided."))

# ------------------------------------------------------------------------------
# Main Page Layout
# ------------------------------------------------------------------------------
if st.session_state.new_profile:
    # Render the newly created profile from Brew Link or AI Barista
    if isinstance(st.session_state.new_profile, dict) and "dose_grams" in st.session_state.new_profile:
        render_espresso_profile_editor(st.session_state.new_profile, profile_key="new_espresso")
    else:
        render_profile_editor(st.session_state.new_profile, profile_key="new")
elif st.session_state.selected_profile_index is not None:
    # Render an existing profile
    idx = st.session_state.selected_profile_index
    profiles_list = st.session_state.brewer_settings.get("profiles", [])
    if 0 <= idx < len(profiles_list):
        p_data = profiles_list[idx]
        if isinstance(p_data, dict):
            if "dose_grams" in p_data:
                render_espresso_profile_editor(p_data, profile_key=f"espresso_{idx}")
            else:
                render_profile_editor(p_data, profile_key=f"existing_{idx}")
        else:
            st.write("### Profile Data")
            st.write(p_data)
else:
    st.write("No profile selected or created.")