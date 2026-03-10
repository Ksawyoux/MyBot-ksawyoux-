import pytest
from src.output.templates.responses.structured_result import StructuredResultTemplate
from src.output.core.types import BlockType, TaskCategory

def test_structured_result_email_parsing():
    email_data = {
        "emails": [
            {
                "id": "1",
                "subject": "Test Email",
                "from": "sender@test.com",
                "date": "2026-03-10",
                "body_preview": "Hello world"
            }
        ]
    }
    # Test with dict
    template = StructuredResultTemplate(data=email_data, task_id="123")
    output = template.render()
    
    assert output.category == TaskCategory.COMPLEX
    assert output.content.primary.text == "📧 *Recent Emails Found*"
    assert len(output.content.supplementary) == 1
    assert output.content.supplementary[0].block_type == BlockType.CARD
    assert output.content.supplementary[0].title == "Test Email"

def test_structured_result_string_parsing():
    # Test with stringified JSON
    email_json = '{"emails": [{"subject": "JSON Email", "from": "bot@test.com"}]}'
    template = StructuredResultTemplate(data=email_json)
    output = template.render()
    
    assert output.content.primary.text == "📧 *Recent Emails Found*"
    assert output.content.supplementary[0].title == "JSON Email"

def test_structured_result_python_literal_parsing():
    # Test with stringified Python literal (common in CrewAI)
    email_repr = "{'emails': [{'subject': 'Python Email', 'from': 'crew@test.com'}]}"
    template = StructuredResultTemplate(data=email_repr)
    output = template.render()
    
    assert output.content.primary.text == "📧 *Recent Emails Found*"
    assert output.content.supplementary[0].title == "Python Email"

def test_structured_result_list_fallback():
    data = ["item1", "item2"]
    template = StructuredResultTemplate(data=data)
    output = template.render()
    
    assert output.content.primary.text == "📋 *Results*"
    assert output.content.supplementary[0].block_type == BlockType.LIST
    assert len(output.content.supplementary[0].items) == 2

def test_structured_result_dict_fallback():
    data = {"key": "value"}
    template = StructuredResultTemplate(data=data)
    output = template.render()
    
    assert output.content.primary.text == "🔍 *Details Found*"
    assert len(output.content.supplementary[0].items) == 1
