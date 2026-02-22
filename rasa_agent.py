"""
RASA integration for NHS Inform RAG agent.

This module integrates RASA NLU for intent classification and entity extraction
with the existing RAG-based health Q&A system. When RASA is not installed
(Python 3.13 or missing package), a built-in simple intent classifier is used.
"""

import asyncio
import json
import re
import time
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

# #region debug log
def _dbg(loc: str, msg: str, data: dict, hid: str) -> None:
    try:
        p = Path(__file__).parent / "debug-088e07.log"
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessionId": "088e07", "location": loc, "message": msg, "data": data, "hypothesisId": hid, "timestamp": round(time.time() * 1000)}) + "\n")
    except Exception:
        pass
# #endregion

try:
    from rasa.core.agent import Agent
    HAS_RASA = True
except ImportError:
    HAS_RASA = False

from agent import answer, REFUSAL_STRATEGIES


# --- Simple intent classifier (no RASA required) ---
INTENT_PATTERNS = {
    "request_appointment": [
        r"\b(book|schedule|make|get)\s+(an?\s+)?appointment",
        r"appointment\s+(with|to see)\s+(a\s+)?(doctor|gp)",
        r"see\s+(a\s+)?(doctor|gp)",
        r"want\s+to\s+(see|visit)\s+(a\s+)?(doctor|gp)",
    ],
    "ask_personal_advice": [
        r"\bshould\s+I\s+",
        r"\bam\s+I\s+(okay|ok|fine)\s*\??",
        r"\bdo\s+I\s+need\s+to\s+see",
        r"\bis\s+this\s+normal\s*\??",
        r"\bwhat\s+should\s+I\s+do\s*\??",
    ],
    "greeting": [
        r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening))\s*!?\s*$",
    ],
    "goodbye": [
        r"^(bye|goodbye|see\s+you|thanks?\s*bye|thank\s+you)\s*!?\s*$",
    ],
    "out_of_scope": [
        r"weather|joke|what time|order\s+pizza|play\s+music|\d+\s*\+\s*\d+",
    ],
}

# Entity extraction: simple pattern for [condition] or "condition" in health questions
CONDITION_ENTITY_PATTERN = re.compile(
    r"\b(what is|tell me about|information on|symptoms of|treat(?:ment)?\s+for|"
    r"prevent(?:ion)?\s+of|about)\s+([a-z0-9\s\-]+?)(?:\?|$|\.|,|\s+and\s+)",
    re.I,
)


def _simple_intent_and_entities(text: str) -> Tuple[Optional[str], List[Dict], float]:
    """Lightweight intent + entity extraction without RASA. Returns (intent, entities, confidence)."""
    text_lower = text.strip().lower()
    entities = []

    for intent, patterns in INTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text_lower, re.I):
                conf = 0.85 if intent in ("greeting", "goodbye") else 0.75
                return intent, entities, conf

    # Try to extract condition/symptom for health intents
    m = CONDITION_ENTITY_PATTERN.search(text_lower)
    if m:
        entity_val = m.group(2).strip()
        if len(entity_val) > 1 and entity_val not in ("a", "an", "the"):
            entities.append({"entity": "condition", "value": entity_val})

    # Default: treat as health question
    health_keywords = [
        "symptom", "treatment", "cause", "prevent", "diagnos", "condition",
        "disease", "illness", "what is", "tell me", "how to", "information",
        "headache", "fever", "pain", "diabetes", "asthma", "flu", "covid",
    ]
    if any(k in text_lower for k in health_keywords) or entities:
        return "ask_about_condition", entities, 0.7
    return None, entities, 0.5


class RasaHealthAgent:
    """
    RASA-powered health information agent that combines:
    - RASA NLU for intent classification and entity extraction
    - RAG system for retrieving NHS Inform content
    - Refusal logic for out-of-scope queries
    """
    
    def __init__(self, rasa_model_path: Optional[str] = None, use_rasa: bool = True):
        """
        Initialize the RASA health agent.
        
        Args:
            rasa_model_path: Path to trained RASA model. If None, uses default location or simple classifier.
            use_rasa: Whether to try RASA first (if False, uses built-in simple intent classifier).
        """
        # #region agent log
        _dbg("RasaHealthAgent.__init__", "entry", {"use_rasa_arg": use_rasa, "HAS_RASA": HAS_RASA}, "H1")
        # #endregion
        self.use_rasa = use_rasa and HAS_RASA
        self.agent = None
        
        if self.use_rasa:
            if rasa_model_path is None:
                models_dir = Path(__file__).parent / "models"
                if models_dir.exists():
                    model_dirs = sorted(models_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if model_dirs:
                        rasa_model_path = str(model_dirs[0])
                else:
                    rasa_model_path = None
            if rasa_model_path:
                try:
                    self.agent = Agent.load(rasa_model_path)
                    # #region agent log
                    _dbg("RasaHealthAgent.__init__", "RASA loaded", {"path": rasa_model_path}, "H1")
                    # #endregion
                except Exception as e:
                    # #region agent log
                    _dbg("RasaHealthAgent.__init__", "RASA load failed", {"error": str(e)}, "H1")
                    # #endregion
                    print(f"Warning: Could not load RASA model: {e}")
                    print("Using built-in intent classifier instead.")
                    self.use_rasa = False
            else:
                self.use_rasa = False
        # #region agent log
        _dbg("RasaHealthAgent.__init__", "exit", {"use_rasa": self.use_rasa, "agent_is_none": self.agent is None}, "H1")
        # #endregion
    
    async def process_message_async(self, message: str, refusal_strategy: str = "explain") -> Dict[str, Any]:
        """
        Process a user message asynchronously using RASA + RAG (or simple intent + RAG).
        
        Returns:
            Dictionary with keys: answer, refused, sources, intent, entities, strategy
        """
        # #region agent log
        _dbg("process_message_async", "entry", {"message_len": len(message)}, "H4")
        # #endregion
        intent, entities, confidence = None, [], 0.0

        if self.use_rasa and self.agent:
            try:
                rasa_result = await self.agent.parse_message(message)
                intent = rasa_result.get("intent", {}).get("name")
                entities = rasa_result.get("entities", [])
                confidence = rasa_result.get("intent", {}).get("confidence", 0.0)
            except Exception as e:
                # #region agent log
                _dbg("process_message_async", "RASA parse error", {"error": str(e)}, "H4")
                # #endregion
                print(f"RASA parsing error: {e}")
                intent, entities, confidence = _simple_intent_and_entities(message)
        else:
            intent, entities, confidence = _simple_intent_and_entities(message)
        # #region agent log
        _dbg("process_message_async", "intent resolved", {"intent": intent, "confidence": confidence, "entities_count": len(entities)}, "H5")
        # #endregion
        # Handle non-health intents (from RASA or simple classifier)
        if intent == "greeting":
            return {
                "answer": "Hello! I'm a health information assistant. I can help answer questions about health conditions, symptoms, treatments, and prevention using information from NHS Inform. How can I help you today?",
                "refused": False,
                "sources": [],
                "intent": intent,
                "entities": entities,
                "strategy": refusal_strategy,
                "confidence": confidence,
            }
        if intent == "goodbye":
            return {
                "answer": "Goodbye! Remember, for personal medical advice, always consult your GP or GP practice. Take care!",
                "refused": False,
                "sources": [],
                "intent": intent,
                "entities": entities,
                "strategy": refusal_strategy,
                "confidence": confidence,
            }
        if intent in ["request_appointment", "ask_personal_advice", "out_of_scope"]:
            if intent == "request_appointment":
                refusal_msg = "I can't help with booking appointments. Please contact your GP practice directly to schedule an appointment."
            elif intent == "ask_personal_advice":
                refusal_msg = REFUSAL_STRATEGIES.get(refusal_strategy, REFUSAL_STRATEGIES["explain"])
            else:
                refusal_msg = "I'm a health information assistant focused on NHS Inform content. I can't help with that. For health questions, please ask about conditions, symptoms, treatments, or prevention."
            return {
                "answer": refusal_msg,
                "refused": True,
                "sources": [],
                "intent": intent,
                "entities": entities,
                "strategy": refusal_strategy,
                "confidence": confidence,
            }
        
        # For health-related intents, use RAG
        # Enhance query with extracted entities if available
        query = message
        if entities:
            # Add entity information to query for better retrieval
            entity_texts = [e.get("value", "") for e in entities if e.get("value")]
            if entity_texts:
                query = f"{message} {' '.join(entity_texts)}"
        # #region agent log
        _dbg("process_message_async", "calling answer()", {"query_len": len(query)}, "H2")
        # #endregion
        try:
            result = answer(query, refusal_strategy=refusal_strategy)
        except Exception as e:
            # #region agent log
            _dbg("process_message_async", "answer() raised", {"error": str(e)}, "H2")
            # #endregion
            raise
        # #region agent log
        _dbg("process_message_async", "answer() returned", {"keys": list(result.keys()) if isinstance(result, dict) else "not_dict", "refused": result.get("refused") if isinstance(result, dict) else None}, "H5")
        # #endregion
        result["intent"] = intent or "ask_about_condition"
        result["entities"] = entities
        result["confidence"] = confidence
        return result
    
    def process_message(self, message: str, refusal_strategy: str = "explain") -> Dict[str, Any]:
        """
        Synchronous wrapper: uses RASA if available, else simple intent classifier + RAG.
        """
        # #region agent log
        _dbg("process_message", "asyncio.run entry", {}, "H4")
        # #endregion
        try:
            out = asyncio.run(self.process_message_async(message, refusal_strategy))
            # #region agent log
            _dbg("process_message", "asyncio.run exit", {"has_answer": "answer" in out}, "H4")
            # #endregion
            return out
        except Exception as e:
            # #region agent log
            _dbg("process_message", "asyncio.run failed", {"error": str(e)}, "H4")
            # #endregion
            raise


def train_rasa_model():
    """Train a RASA model from the configuration files."""
    if not HAS_RASA:
        print("RASA not installed. Install with: pip install rasa>=3.6.0")
        return
    
    from rasa import train
    
    config_path = Path(__file__).parent / "rasa_config.yml"
    domain_path = Path(__file__).parent / "domain.yml"
    training_files = [
        Path(__file__).parent / "data" / "nlu.yml",
        Path(__file__).parent / "data" / "stories.yml",
        Path(__file__).parent / "data" / "rules.yml",
    ]
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not domain_path.exists():
        raise FileNotFoundError(f"Domain file not found: {domain_path}")
    
    print("Training RASA model...")
    model_path = train(
        domain=str(domain_path),
        config=str(config_path),
        training_files=[str(f) for f in training_files if f.exists()],
        output=str(Path(__file__).parent / "models"),
    )
    print(f"Model trained and saved to: {model_path}")
    return model_path


def main():
    """Main entry point for RASA agent."""
    import argparse
    
    parser = argparse.ArgumentParser(description="RASA-powered NHS Inform health agent")
    parser.add_argument("command", choices=["train", "chat"], default="chat", nargs="?",
                       help="train: train RASA model; chat: interactive chat")
    parser.add_argument("--model", type=str, help="Path to RASA model")
    parser.add_argument("--refusal-strategy", choices=list(REFUSAL_STRATEGIES), default="explain",
                       help="Refusal message strategy")
    parser.add_argument("--no-rasa", action="store_true", help="Disable RASA, use direct RAG only")
    
    args = parser.parse_args()
    
    # #region agent log
    _dbg("main", "args", {"command": args.command, "no_rasa": getattr(args, "no_rasa", False)}, "H1")
    # #endregion
    if args.command == "train":
        train_rasa_model()
        return
    
    # Chat mode
    print("Loading agent...")
    agent = RasaHealthAgent(rasa_model_path=args.model, use_rasa=not args.no_rasa)
    if agent.use_rasa and agent.agent:
        print("RASA model loaded. Ask health questions (or 'quit').\n")
    else:
        print("Using built-in intent classifier + NHS Inform RAG. Ask health questions (or 'quit').\n")
    
    while True:
        try:
            message = input("You: ").strip()
        except EOFError:
            break
        
        if not message or message.lower() in ("quit", "exit", "q"):
            break
        
        result = agent.process_message(message, refusal_strategy=args.refusal_strategy)
        
        print(f"\nAgent: {result['answer']}")
        if result.get("intent"):
            print(f"  Intent: {result['intent']} (confidence: {result.get('confidence', 0):.2f})")
        if result.get("entities"):
            print(f"  Entities: {[e.get('value') for e in result['entities']]}")
        if result.get("sources"):
            print(f"  Sources: {result['sources'][:3]}")
        print()


if __name__ == "__main__":
    main()
