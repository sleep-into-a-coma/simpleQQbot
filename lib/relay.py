"""Model relay: detect cross-model conversation handoffs and generate relay prompts."""


def detect_relay(history: list[dict], current_model_name: str) -> str | None:
    """
    Scan history for assistant messages from a different model.
    Returns relay prompt string if a switch is detected, else None.
    """
    previous_models: set[str] = set()
    for h in history:
        if h["role"] == "assistant":
            model = h.get("model_name")
            if model and model != current_model_name:
                previous_models.add(model)

    if not previous_models:
        return None

    prev_list = ", ".join(sorted(previous_models))
    return (
        f"[接力提示] 之前的回复由模型 {prev_list} 生成，"
        f"现在由你（{current_model_name}）继续。"
        f"请保持对话风格和上下文的连贯。"
    )
