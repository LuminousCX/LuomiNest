import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from app.engines.memory.memory_engine import MemoryEngine, FactItem, ProfileData, SummaryData

@pytest.fixture
def temp_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def memory_engine(temp_storage):
    return MemoryEngine(storage_path=temp_storage)

class TestMemoryEngine:
    def test_initialization(self, memory_engine):
        assert memory_engine._path.exists()
        assert (memory_engine._path / "daily").exists()

    def test_load_empty_data(self, memory_engine):
        data = memory_engine.load_data()
        assert data.version == "2.0"
        assert data.profile.name == ""
        assert data.facts == []
        assert isinstance(data.summaries, SummaryData)

    def test_add_and_get_fact(self, memory_engine):
        fact = FactItem(content="Test fact", category="preference", confidence=0.9)
        memory_engine.add_fact(fact)
        
        facts = memory_engine.get_facts()
        assert len(facts) == 1
        assert facts[0].content == "Test fact"
        assert facts[0].category == "preference"
        assert facts[0].confidence == 0.9

    def test_add_duplicate_fact(self, memory_engine):
        fact1 = FactItem(content="Same fact", category="context", confidence=0.8)
        fact2 = FactItem(content="Same fact", category="preference", confidence=0.9)
        
        memory_engine.add_fact(fact1)
        memory_engine.add_fact(fact2)
        
        facts = memory_engine.get_facts()
        assert len(facts) == 1
        assert facts[0].category == "preference"
        assert facts[0].confidence == 0.9

    def test_remove_fact(self, memory_engine):
        fact = FactItem(content="To be removed", category="context", confidence=0.8)
        memory_engine.add_fact(fact)
        
        assert len(memory_engine.get_facts()) == 1
        result = memory_engine.remove_fact(fact.id)
        assert result is True
        assert len(memory_engine.get_facts()) == 0

    def test_remove_nonexistent_fact(self, memory_engine):
        result = memory_engine.remove_fact("nonexistent_id")
        assert result is False

    def test_update_fact(self, memory_engine):
        fact = FactItem(content="Original", category="context", confidence=0.8)
        memory_engine.add_fact(fact)
        
        result = memory_engine.update_fact(fact.id, content="Updated", confidence=0.95)
        assert result is True
        
        updated_fact = memory_engine.get_facts()[0]
        assert updated_fact.content == "Updated"
        assert updated_fact.confidence == 0.95

    def test_update_nonexistent_fact(self, memory_engine):
        result = memory_engine.update_fact("nonexistent_id", content="Test")
        assert result is False

    def test_fact_limit(self, memory_engine):
        for i in range(110):
            fact = FactItem(content=f"Fact {i}", category="context", confidence=0.5 + (i % 50) * 0.01)
            memory_engine.add_fact(fact)
        
        facts = memory_engine.get_facts()
        assert len(facts) == 100
        assert all(f.confidence >= 0.5 for f in facts)

    def test_save_and_load_profile(self, memory_engine):
        data = memory_engine.load_data()
        data.profile.name = "TestUser"
        memory_engine.save_data(data)
        
        memory_engine._cache = None
        loaded = memory_engine.load_data()
        assert loaded.profile.name == "TestUser"

    def test_build_context_with_profile(self, memory_engine):
        data = memory_engine.load_data()
        data.profile.name = "John"
        memory_engine.save_data(data)
        
        context = memory_engine.build_context()
        assert "John" in context
        assert "用户档案" in context

    def test_build_context_with_facts(self, memory_engine):
        fact = FactItem(content="John likes coffee", category="preference", confidence=0.9)
        memory_engine.add_fact(fact)
        
        context = memory_engine.build_context()
        assert "John likes coffee" in context
        assert "记忆事实" in context

    def test_daily_operations(self, memory_engine):
        memory_engine.append_daily("Test daily entry")
        content = memory_engine.load_daily()
        assert "Test daily entry" in content
        
        dailies = memory_engine.list_dailies()
        assert len(dailies) == 1

    def test_clear_operations(self, memory_engine):
        fact = FactItem(content="Test", category="context", confidence=0.8)
        memory_engine.add_fact(fact)
        memory_engine.append_daily("Test")
        memory_engine.save_knowledge("Test knowledge")
        
        memory_engine.clear_facts()
        assert len(memory_engine.get_facts()) == 0
        
        memory_engine.clear_dailies()
        assert len(memory_engine.list_dailies()) == 0
        
        memory_engine.clear_knowledge()
        assert memory_engine.load_knowledge() == ""

    def test_deprecate_old_name_facts(self, memory_engine):
        old_name_fact = FactItem(content="我的名字是小红", category="context", confidence=0.95)
        new_name_fact = FactItem(content="我叫小明", category="context", confidence=0.95)
        unrelated_fact = FactItem(content="我喜欢咖啡", category="preference", confidence=0.9)
        
        memory_engine.add_fact(old_name_fact)
        memory_engine.add_fact(new_name_fact)
        memory_engine.add_fact(unrelated_fact)
        
        data = memory_engine.load_data()
        memory_engine._deprecate_old_name_facts(data, "小红", "小明")
        memory_engine.save_data(data)
        
        facts = memory_engine.get_facts()
        old_name_fact_result = next(f for f in facts if "小红" in f.content)
        assert old_name_fact_result.confidence == 0.3
        
        new_name_fact_result = next(f for f in facts if "小明" in f.content)
        assert new_name_fact_result.confidence == 0.95
        
        unrelated_fact_result = next(f for f in facts if "咖啡" in f.content)
        assert unrelated_fact_result.confidence == 0.9

    def test_find_similar_fact(self, memory_engine):
        fact = FactItem(content="Hello World", category="context", confidence=0.8)
        memory_engine.add_fact(fact)
        
        data = memory_engine.load_data()
        found = memory_engine._find_similar_fact(data, "hello world")
        assert found is not None
        assert found.content == "Hello World"
        
        not_found = memory_engine._find_similar_fact(data, "different")
        assert not_found is None

@pytest.mark.asyncio
async def test_extract_facts_empty(memory_engine):
    name, facts = await memory_engine.extract_facts("")
    assert name == ""
    assert facts == []

@pytest.mark.asyncio
async def test_extract_facts_with_mock_llm(memory_engine):
    mock_adapter = AsyncMock()
    mock_adapter.chat.return_value = '{"profile_name": "TestName", "facts": [{"content": "Test fact", "category": "preference", "confidence": 0.9}]}'
    
    name, facts = await memory_engine.extract_facts("My name is TestName and I like coffee", llm_adapter=mock_adapter)
    
    assert name == "TestName"
    assert len(facts) == 1
    assert facts[0].content == "Test fact"

@pytest.mark.asyncio
async def test_update_profile_from_message(memory_engine):
    mock_adapter = AsyncMock()
    mock_adapter.chat.return_value = '{"profile_name": "NewName", "facts": [{"content": "New fact", "category": "preference", "confidence": 0.9}]}'
    
    result = await memory_engine.update_profile_from_message("My name is NewName", llm_adapter=mock_adapter)
    
    assert "name" in result
    assert result["name"] == "NewName"
    
    data = memory_engine.load_data()
    assert data.profile.name == "NewName"
    assert len(data.facts) == 1

@pytest.mark.asyncio
async def test_distill_conversation(memory_engine):
    mock_adapter = AsyncMock()
    mock_adapter.chat.return_value = '''{
        "profile_name": "",
        "facts": [{"content": "Distilled fact", "category": "context", "confidence": 0.9}],
        "summary": {"用户画像": "- Test user", "偏好设置": "", "兴趣目标": "", "近期状态": "", "事件时间线": ""}
    }'''
    
    messages = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
    result = await memory_engine.distill_conversation(messages, llm_adapter=mock_adapter)
    
    assert result is not None
    assert "Test user" in result
    
    data = memory_engine.load_data()
    assert len(data.facts) == 1