# RASA Integration Guide

This project now integrates **RASA** (Reasonable Assistant) for intent classification and entity extraction, enhancing the NHS Inform RAG agent with better understanding of user queries.

## What RASA Adds

1. **Intent Classification**: Understands what the user wants (ask about condition, request appointment, greeting, etc.)
2. **Entity Extraction**: Extracts medical conditions, symptoms, and other entities from user queries
3. **Conversation Management**: Handles multi-turn conversations and context
4. **Smart Refusal**: Better detection of out-of-scope queries (appointments, personal advice, non-health questions)

## Architecture

```
User Query
    ↓
RASA NLU (Intent + Entities)
    ↓
Intent-based Routing
    ├─ Health Questions → RAG System → LLM Answer
    ├─ Appointments → Direct Refusal
    ├─ Personal Advice → Refusal with Strategy
    └─ Out of Scope → Refusal
```

## Setup

### Option A: Use without installing RASA (recommended for Python 3.12+)

The agent includes a **built-in simple intent classifier**, so you can use intent-based routing without installing RASA:

```bash
python rasa_agent.py chat
```

This uses keyword/regex patterns for intents (greeting, request_appointment, ask_about_condition, etc.) and your existing RAG for answers. No extra install needed.

### Option B: Full RASA (Python 3.10 or 3.11 only)

RASA and its ML stack (e.g. DIETClassifier) support **Python 3.10 or 3.11**. On Python 3.12/3.13, use Option A.

1. **Use Python 3.10 or 3.11** (e.g. create a venv):
   ```bash
   py -3.11 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Train RASA model**:
   ```bash
   python rasa_agent.py train
   ```
   This creates a trained model in the `models/` directory.

3. **Use the agent** (with or without a trained model):
   ```bash
   python rasa_agent.py chat
   python rasa_agent.py chat --refusal-strategy explain
   python rasa_agent.py chat --no-rasa   # force built-in classifier only
   ```

## RASA Configuration Files

- **`rasa_config.yml`**: Pipeline configuration (DIET classifier for intents/entities)
- **`domain.yml`**: Defines intents, entities, responses, and actions
- **`data/nlu.yml`**: Training examples for intents and entities
- **`data/stories.yml`**: Conversation flows
- **`data/rules.yml`**: Simple rules for specific intents

## Supported Intents

1. **`ask_about_condition`**: Questions about medical conditions
   - Example: "What is diabetes?", "Tell me about asthma"

2. **`ask_about_symptoms`**: Questions about symptoms
   - Example: "What are the symptoms of fever?"

3. **`ask_about_treatment`**: Questions about treatments
   - Example: "How to treat diabetes?"

4. **`ask_about_prevention`**: Questions about prevention
   - Example: "How to prevent flu?"

5. **`request_appointment`**: Booking requests (always refused)
   - Example: "I need to book an appointment"

6. **`ask_personal_advice`**: Personal medical advice (always refused)
   - Example: "Should I take this medicine?"

7. **`greeting`**: Greetings
   - Example: "Hello", "Hi"

8. **`goodbye`**: Farewells
   - Example: "Bye", "Goodbye"

9. **`out_of_scope`**: Non-health questions (always refused)
   - Example: "What's the weather?"

## Entities Extracted

- **`condition`**: Medical conditions (diabetes, asthma, flu, etc.)
- **`symptom`**: Symptoms (headache, fever, cough, etc.)

## Integration with Existing System

The RASA agent (`rasa_agent.py`) integrates seamlessly with your existing RAG system:

- Uses `rag.py` for document retrieval
- Uses `agent.py`'s `answer()` function for generating responses
- Maintains all refusal strategies
- Adds intent/entity information to responses

## Example Usage

```python
from rasa_agent import RasaHealthAgent

# Initialize agent
agent = RasaHealthAgent()

# Process a message
result = agent.process_message("What are the symptoms of diabetes?")

print(result["answer"])        # LLM-generated answer
print(result["intent"])        # "ask_about_condition"
print(result["entities"])      # [{"entity": "condition", "value": "diabetes"}]
print(result["sources"])       # URLs from NHS Inform
```

## Customization

### Add New Intents

1. Add examples to `data/nlu.yml`:
```yaml
- intent: ask_about_diagnosis
  examples: |
    - how is [condition](condition) diagnosed?
    - diagnosis of [asthma](condition)
```

2. Add intent to `domain.yml`:
```yaml
intents:
  - ask_about_diagnosis
```

3. Add story to `data/stories.yml`:
```yaml
- story: ask about diagnosis
  steps:
  - intent: ask_about_diagnosis
  - action: action_answer_health_question
```

4. Retrain: `python rasa_agent.py train`

### Modify Entity Extraction

Edit `data/nlu.yml` to add more entity examples or create new entity types.

## Benefits Over Direct RAG

1. **Better Query Understanding**: Intent classification helps route queries correctly
2. **Entity Extraction**: Extracted conditions/symptoms can enhance retrieval
3. **Structured Refusal**: Clear rules for when to refuse (appointments, personal advice)
4. **Conversation Flow**: Can handle multi-turn conversations
5. **Extensibility**: Easy to add new intents and behaviors

## Troubleshooting

### Model Not Found / RASA not installed
You don't need a model to run the agent. Just run `python rasa_agent.py chat`; the built-in intent classifier will be used.

### RASA Install Fails (e.g. on Python 3.13)
RASA's full stack requires **Python 3.10 or 3.11**. On newer Python, use the built-in classifier (no install). To use full RASA, create a venv with Python 3.11 and install there.

### Fallback Mode
If RASA is not installed or the model fails to load, the agent uses the built-in intent classifier and your existing RAG (same answer quality, with intent/entity info from patterns).

## Next Steps

1. **Expand Training Data**: Add more examples to `data/nlu.yml` for better accuracy
2. **Add More Intents**: Consider intents like `ask_about_medication`, `ask_about_tests`
3. **Multi-turn Conversations**: Enhance stories for follow-up questions
4. **Entity Synonyms**: Add synonyms for common conditions/symptoms
5. **Evaluation**: Test RASA accuracy vs direct RAG on your evaluation set
