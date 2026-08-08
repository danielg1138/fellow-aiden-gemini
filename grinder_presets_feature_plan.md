# Feature Spec & Implementation Plan: Grinder Presets & AI Grind Recommendations

This document contains a complete technical specification and step-by-step instructions to implement **Grinder Presets & AI Grind Size Recommendations** in the Fellow Aiden Brew Studio app.

---

## 1. Feature Overview

Fellow Aiden handles brewing temperatures and pulse timings automatically, but grind size must be dialed in by the user on their home grinder.

This feature adds:
1. **User Grinder Selection**: A dropdown in the Brew Studio sidebar allowing users to select their specific grinder (e.g. *Fellow Ode Gen 2*, *Baratza Encore*, *Comandante C40*, *1Zpresso K-Ultra*, *Timemore C2/C3*).
2. **AI Grind Size Physics Engine**: Instructions added to Gemini Vision & Text prompts to calculate the exact dial setting number based on roast density, bean process (washed, natural, anaerobic), and fines generation.
3. **Prominent Grind Display Card**: A dedicated UI banner at the top of the Brew Profile editor displaying the exact dial setting and rationale.

---

## 2. Technical Context & Prompt Instructions

### AI System Prompt Addition
Update the `SYSTEM` prompt in `brew_studio/brew_studio.py` to include:

```text
Grinder Dial Settings Knowledge:
You are an expert on home coffee grinders. When given a coffee description or image, analyze roast density, process, and altitude, and determine the optimal grind size in microns (600-800µm for pour over).

Calculate the exact setting for the user's specific grinder model using these calibration curves:
- Fellow Ode Gen 2: Range 3.0 to 6.0 (e.g., 3.2 for light washed, 4.1 for medium, 5.1 for natural/dark).
- Fellow Ode Gen 1: Range 1.2 to 3.2.
- Baratza Encore: Range 14 to 22 (e.g., 15 for light, 18 for medium).
- Comandante C40: Range 20 to 26 clicks.
- 1Zpresso K-Ultra: Range 6.0 to 7.5.
- Timemore C2/C3: Range 15 to 22 clicks.

Include a section titled "GRIND RECOMMENDATION" at the top of your explanation with the setting number and brief rationale.
```

---

## 3. Code Implementation Details

### Changes to `brew_studio/brew_studio.py`

#### A. Sidebar Grinder Selector & Secrets Auto-Save
In the sidebar section of `brew_studio.py`:

```python
# Grinder Selection
GRINDER_MODELS = [
    "Fellow Ode (Gen 2)",
    "Fellow Ode (Gen 1)",
    "Baratza Encore / Virtuoso",
    "Comandante C40",
    "1Zpresso K-Series",
    "Timemore C2/C3",
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
```

#### B. Pass Grinder Model to Gemini
In `generate_gemini_recipe_and_explanation` and `generate_gemini_vision_recipe_and_explanation`, pass the selected grinder to Gemini:

```python
prompt += f"\nUser's Grinder Model: {selected_grinder}. Provide the exact dial setting number for this grinder."
```

#### C. Render Recommendation Banner in Profile Editor
Inside `render_profile_editor(profile_dict)`:

```python
# Display Grind Size Recommendation Banner if present
description_text = profile_dict.get("description", "")
if "GRIND RECOMMENDATION" in description_text.upper() or "SETTING" in description_text.upper():
    st.info(f"⚙️ **Grinder Setting for {st.session_state.get('selected_grinder', 'Your Grinder')}**\n\nSee full rationale in Description below.")
```

---

## 4. How to Apply This Plan on Your Desktop PC

When setting up or updating Antigravity on your Desktop PC:
1. Open your desktop project folder in Antigravity.
2. Provide the contents of this file or type:
   > *"Implement the Grinder Presets & AI Grind Size Recommendations feature described in `grinder_presets_feature_plan.md`."*
3. Antigravity will update `brew_studio.py` and run tests automatically!
