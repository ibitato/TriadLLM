from multibrainllm.domain import ConsolidatedResponse


def test_consolidated_response_coerces_nested_text_fields() -> None:
    result = ConsolidatedResponse.model_validate(
        {
            "processor_view": {"message": "processor text"},
            "validator_view": ["validator", "text"],
            "synthesis": {"respuesta_final": "final text"},
        }
    )

    assert result.processor_view == "processor text"
    assert result.validator_view == "validator\ntext"
    assert result.synthesis == "final text"
