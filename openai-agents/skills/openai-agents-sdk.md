# OpenAI Agent SDK Complete Reference

> **최신 정보 필요 시**: Context7 MCP를 통해 조회 (Library ID: `/openai/openai-agents-python`)

## Overview

OpenAI Agents SDK는 multi-agent 워크플로우를 구축하기 위한 프레임워크입니다.

### Core Primitives
- **Agents**: Instructions와 tools를 갖춘 LLM
- **Handoffs**: Agent 간 작업 위임
- **Guardrails**: 입출력 검증
- **Sessions**: 대화 히스토리 및 상태 관리
- **Tracing**: 디버깅 및 모니터링

### Installation

```bash
pip install openai-agents
# 또는 extras와 함께
pip install openai-agents[litellm]  # LiteLLM 지원
pip install openai-agents[voice]    # Voice 지원
```

---

## 1. Agents

### Basic Agent Creation

```python
from agents import Agent, Runner

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant",
    model="gpt-4.1",  # 기본값
)

# 동기 실행
result = Runner.run_sync(agent, "Hello!")
print(result.final_output)

# 비동기 실행
result = await Runner.run(agent, "Hello!")
```

### Agent Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Agent 식별자 (필수) |
| `instructions` | `str \| Callable` | 시스템 프롬프트. 동적 함수 가능: `(context, agent) -> str` |
| `model` | `str` | 사용할 LLM 모델 |
| `model_settings` | `ModelSettings` | temperature, top_p, tool_choice 등 |
| `tools` | `list[Tool]` | 사용 가능한 도구 목록 |
| `mcp_servers` | `list[MCPServer]` | MCP 서버 목록 |
| `handoffs` | `list[Agent \| Handoff]` | 위임 가능한 다른 Agent |
| `input_guardrails` | `list[InputGuardrail]` | 입력 검증 guardrail |
| `output_guardrails` | `list[OutputGuardrail]` | 출력 검증 guardrail |
| `output_type` | `type` | 출력 타입 (Pydantic, dataclass 등) |
| `handoff_description` | `str` | Handoff 시 표시되는 설명 |
| `reset_tool_choice` | `bool` | Tool 사용 후 tool_choice 리셋 (기본: True) |

### Dynamic Instructions

```python
def get_instructions(context: RunContextWrapper, agent: Agent) -> str:
    user_name = context.context.user_name
    return f"You are helping {user_name}. Be friendly and helpful."

agent = Agent(
    name="PersonalAssistant",
    instructions=get_instructions,
)
```

### Model Settings

```python
from agents import Agent, ModelSettings

agent = Agent(
    name="Assistant",
    model="gpt-5.2",
    model_settings=ModelSettings(
        temperature=0.7,
        top_p=0.9,
        tool_choice="auto",  # "auto" | "required" | "none" | specific_tool_name
        reasoning={"effort": "medium"},  # GPT-5.x용
    ),
)
```

### Structured Output

```python
from pydantic import BaseModel

class CalendarEvent(BaseModel):
    title: str
    date: str
    participants: list[str]

agent = Agent(
    name="Scheduler",
    instructions="Extract calendar events from user input",
    output_type=CalendarEvent,
)

result = Runner.run_sync(agent, "Meeting with John tomorrow at 3pm")
event: CalendarEvent = result.final_output
```

### Tool Use Behavior

```python
from agents import Agent, StopAtTools, ToolsToFinalOutputFunction

# 첫 번째 tool 결과를 최종 출력으로
agent = Agent(
    name="Agent",
    tool_use_behavior="stop_on_first_tool",
)

# 특정 tool에서 멈춤
agent = Agent(
    name="Agent",
    tool_use_behavior=StopAtTools(stop_at_tool_names=["final_answer"]),
)

# 커스텀 로직
def custom_behavior(context, tool_results) -> str | None:
    for result in tool_results:
        if result.tool_name == "done":
            return result.output
    return None  # LLM 계속 실행

agent = Agent(
    name="Agent",
    tool_use_behavior=ToolsToFinalOutputFunction(custom_behavior),
)
```

### Agent Cloning

```python
base_agent = Agent(name="Base", instructions="...")
specialized = base_agent.clone(
    name="Specialized",
    instructions="More specific instructions",
)
```

---

## 2. Tools

### 2.1 Function Tools

```python
from agents import function_tool, RunContextWrapper

@function_tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get current weather for a city.

    Args:
        city: The city name to get weather for
        unit: Temperature unit (celsius or fahrenheit)

    Returns:
        Weather information string
    """
    return f"Weather in {city}: 22°{unit[0].upper()}, Sunny"

agent = Agent(
    name="WeatherBot",
    tools=[get_weather],
)
```

### Function Tool Options

```python
@function_tool(
    name_override="fetch_weather",      # 커스텀 tool 이름
    use_docstring_info=True,            # docstring에서 설명 추출 (기본: True)
    failure_error_function=custom_err,  # 에러 핸들러
)
async def get_weather(
    ctx: RunContextWrapper[MyContext],  # 선택적 context 접근
    city: str,
) -> str:
    """..."""
    return f"Weather: {city}"
```

### Return Types

```python
from agents import function_tool, ToolOutputText, ToolOutputImage, ToolOutputFileContent

@function_tool
def text_result() -> str:
    return "Simple text"

@function_tool
def image_result() -> ToolOutputImage:
    return ToolOutputImage(
        image_data=base64_data,
        media_type="image/png",
    )

@function_tool
def file_result() -> ToolOutputFileContent:
    return ToolOutputFileContent(
        file_content=bytes_data,
        media_type="application/pdf",
    )

# 복합 결과
@function_tool
def multi_result() -> list:
    return [
        ToolOutputText(text="Here's the image:"),
        ToolOutputImage(image_data=data, media_type="image/png"),
    ]
```

### Manual Function Tool

```python
from agents import FunctionTool

async def handle_invoke(ctx: ToolContext, args_json: str) -> str:
    args = json.loads(args_json)
    return f"Processed: {args}"

tool = FunctionTool(
    name="custom_tool",
    description="A custom tool",
    params_json_schema={
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input data"}
        },
        "required": ["input"],
    },
    on_invoke_tool=handle_invoke,
)
```

### 2.2 Hosted Tools (OpenAI 서버에서 실행)

```python
from agents import Agent
from agents.tools import (
    WebSearchTool,
    FileSearchTool,
    CodeInterpreterTool,
    ImageGenerationTool,
    HostedMCPTool,
)

agent = Agent(
    name="ResearchBot",
    model="gpt-4.1",  # OpenAIResponsesModel 필요
    tools=[
        WebSearchTool(),
        FileSearchTool(
            vector_store_ids=["vs_123"],
            max_num_results=10,
        ),
        CodeInterpreterTool(),
        ImageGenerationTool(),
        HostedMCPTool(
            server_label="my-server",
            server_url="https://mcp.example.com",
            allowed_tools=["tool1", "tool2"],
        ),
    ],
)
```

### 2.3 Local Runtime Tools

```python
from agents.tools import ComputerTool, LocalShellTool, ApplyPatchTool

# Computer Tool - 구현 필요
class MyComputer:
    async def screenshot(self) -> bytes: ...
    async def click(self, x: int, y: int, button: str): ...
    async def scroll(self, x: int, y: int, dx: int, dy: int): ...
    async def type(self, text: str): ...
    async def keypress(self, keys: list[str]): ...
    async def drag(self, path: list[tuple[int, int]]): ...

computer_tool = ComputerTool(computer=MyComputer())

# Shell Tool
shell_tool = LocalShellTool()

# Patch Tool
patch_tool = ApplyPatchTool(editor=MyPatchEditor())
```

### 2.4 Agents as Tools

```python
from agents import Agent

# 전문 sub-agent
specialist = Agent(
    name="DataAnalyst",
    instructions="You analyze data and provide insights",
)

# 메인 agent가 specialist를 tool로 사용
def extract_summary(result) -> str:
    # RunResult에서 요약 추출
    return result.final_output[:200]

main_agent = Agent(
    name="Manager",
    tools=[
        specialist.as_tool(
            tool_name="analyze_data",
            tool_description="Analyze data and get insights",
            custom_output_extractor=extract_summary,
            is_enabled=True,  # 또는 callable: (ctx, agent) -> bool
        ),
    ],
)
```

### 2.5 MCP Tools

```python
from agents import Agent
from agents.mcp import MCPServerStdio, MCPServerStreamableHttp

# Stdio MCP Server (로컬 프로세스)
async with MCPServerStdio(
    name="Filesystem",
    params={
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
    },
) as server:
    agent = Agent(name="FileBot", mcp_servers=[server])

# HTTP MCP Server (원격)
async with MCPServerStreamableHttp(
    name="RemoteServer",
    params={
        "url": "https://mcp.example.com/mcp",
        "headers": {"Authorization": "Bearer token"},
        "timeout": 30,
    },
    cache_tools_list=True,  # tool 목록 캐싱
    max_retry_attempts=3,
    retry_backoff_seconds_base=2,
) as server:
    agent = Agent(name="RemoteBot", mcp_servers=[server])

    # 캐시 무효화
    await server.invalidate_tools_cache()
```

### 2.6 Codex Tool (Experimental)

```python
from agents.tools import codex_tool

tool = codex_tool(
    sandbox_mode="workspace-write",
    working_directory="/path/to/repo",
    default_thread_options={
        "model": "codex-1",
        "enable_web_search": True,
    },
    persist_session=True,
    skip_git_repo_check=False,
)
```

---

## 3. Context

### Context 정의 및 사용

```python
from dataclasses import dataclass
from agents import Agent, Runner, RunContextWrapper, function_tool

@dataclass
class MyContext:
    user_id: str
    user_name: str
    db_connection: Any
    logger: logging.Logger

@function_tool
async def get_user_data(ctx: RunContextWrapper[MyContext]) -> str:
    user_id = ctx.context.user_id
    db = ctx.context.db_connection
    ctx.context.logger.info(f"Fetching data for {user_id}")
    return await db.fetch_user(user_id)

agent = Agent(
    name="UserBot",
    tools=[get_user_data],
)

# Context와 함께 실행
context = MyContext(
    user_id="123",
    user_name="John",
    db_connection=db,
    logger=logger,
)

result = await Runner.run(agent, "Get my data", context=context)
```

### ToolContext

```python
from agents import ToolContext

@function_tool
async def my_tool(ctx: ToolContext) -> str:
    print(f"Tool name: {ctx.tool_name}")
    print(f"Tool call ID: {ctx.tool_call_id}")
    print(f"Arguments: {ctx.tool_arguments}")
    return "done"
```

---

## 4. Handoffs

### Basic Handoff

```python
from agents import Agent

support_agent = Agent(
    name="Support",
    instructions="Handle customer support inquiries",
    handoff_description="Transfer for support issues",
)

billing_agent = Agent(
    name="Billing",
    instructions="Handle billing questions",
    handoff_description="Transfer for billing issues",
)

router = Agent(
    name="Router",
    instructions="Route users to the appropriate department",
    handoffs=[support_agent, billing_agent],
)
```

### Customized Handoff

```python
from agents import Agent, handoff
from pydantic import BaseModel

class HandoffInput(BaseModel):
    reason: str
    priority: str

async def on_handoff_callback(ctx: RunContextWrapper, input_data: HandoffInput):
    print(f"Handoff reason: {input_data.reason}, Priority: {input_data.priority}")

support_handoff = handoff(
    agent=support_agent,
    tool_name_override="transfer_to_support_team",
    tool_description_override="Transfer to support for technical issues",
    input_type=HandoffInput,
    on_handoff=on_handoff_callback,
    is_enabled=lambda ctx, agent: ctx.context.user_tier == "premium",
)

router = Agent(
    name="Router",
    handoffs=[support_handoff, billing_agent],
)
```

### Input Filters

```python
from agents import handoff, HandoffInputData
from agents.extensions.handoff_filters import remove_all_tools

def custom_filter(data: HandoffInputData) -> HandoffInputData:
    # 히스토리에서 특정 메시지 제거
    filtered_history = [
        item for item in data.history
        if not item.get("sensitive")
    ]
    return HandoffInputData(history=filtered_history)

handoff_config = handoff(
    agent=target_agent,
    input_filter=remove_all_tools,  # 또는 custom_filter
)
```

### Recommended Prompt

```python
from agents import Agent
from agents.extensions.handoff_prompt import (
    RECOMMENDED_PROMPT_PREFIX,
    prompt_with_handoff_instructions,
)

# 방법 1: 직접 prefix 사용
agent = Agent(
    name="Router",
    instructions=RECOMMENDED_PROMPT_PREFIX + "Your specific instructions...",
    handoffs=[...],
)

# 방법 2: 함수 사용
agent = Agent(
    name="Router",
    instructions=prompt_with_handoff_instructions("Your specific instructions..."),
    handoffs=[...],
)
```

---

## 5. Guardrails

### Input Guardrails

```python
from agents import Agent, input_guardrail, GuardrailFunctionOutput, RunContextWrapper

@input_guardrail
async def check_harmful_content(
    ctx: RunContextWrapper,
    agent: Agent,
    input_text: str,
) -> GuardrailFunctionOutput:
    # 유해 콘텐츠 검사 (빠른 모델 사용 권장)
    is_harmful = "harmful" in input_text.lower()

    return GuardrailFunctionOutput(
        output_info={"checked": True},
        tripwire_triggered=is_harmful,
    )

agent = Agent(
    name="SafeBot",
    input_guardrails=[check_harmful_content],
)
```

### Blocking vs Parallel Mode

```python
from agents import InputGuardrail

# Blocking mode - guardrail 완료 후 agent 시작
blocking_guardrail = InputGuardrail(
    guardrail_function=check_harmful_content,
    run_in_parallel=False,  # 토큰 소비 방지
)

# Parallel mode (기본) - 동시 실행, 낮은 latency
parallel_guardrail = InputGuardrail(
    guardrail_function=check_harmful_content,
    run_in_parallel=True,
)
```

### Output Guardrails

```python
from agents import Agent, output_guardrail, GuardrailFunctionOutput

@output_guardrail
async def check_pii(
    ctx: RunContextWrapper,
    agent: Agent,
    output_text: str,
) -> GuardrailFunctionOutput:
    has_pii = detect_pii(output_text)
    return GuardrailFunctionOutput(
        output_info={"pii_detected": has_pii},
        tripwire_triggered=has_pii,
    )

agent = Agent(
    name="SafeBot",
    output_guardrails=[check_pii],
)
```

### Tool Guardrails

```python
from agents import function_tool, tool_input_guardrail, tool_output_guardrail
from agents import ToolGuardrailFunctionOutput

@tool_input_guardrail
async def validate_tool_input(ctx, agent, tool, args) -> ToolGuardrailFunctionOutput:
    if "forbidden" in str(args):
        return ToolGuardrailFunctionOutput.reject_content("Forbidden input detected")
    return ToolGuardrailFunctionOutput.allow()

@tool_output_guardrail
async def validate_tool_output(ctx, agent, tool, result) -> ToolGuardrailFunctionOutput:
    if "error" in result.lower():
        return ToolGuardrailFunctionOutput.reject_content("Tool produced error")
    return ToolGuardrailFunctionOutput.allow()

@function_tool(
    tool_input_guardrails=[validate_tool_input],
    tool_output_guardrails=[validate_tool_output],
)
def my_tool(data: str) -> str:
    return f"Processed: {data}"
```

### Exception Handling

```python
from agents import Runner, InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered

try:
    result = await Runner.run(agent, user_input)
except InputGuardrailTripwireTriggered as e:
    print(f"Input blocked: {e.guardrail_result.output_info}")
except OutputGuardrailTripwireTriggered as e:
    print(f"Output blocked: {e.guardrail_result.output_info}")
```

---

## 6. Sessions

### SQLiteSession

```python
from agents import Agent, Runner
from agents.extensions.session import SQLiteSession

# In-memory (휘발성)
session = SQLiteSession(session_id="user_123")

# File-based (영구 저장)
session = SQLiteSession(
    session_id="user_123",
    db_path="conversations.db",
)

result = await Runner.run(agent, "Hello!", session=session)
result = await Runner.run(agent, "Remember what I said?", session=session)
```

### OpenAIConversationsSession

```python
from agents.extensions.session import OpenAIConversationsSession

# 새 대화
session = OpenAIConversationsSession()

# 기존 대화 이어가기
session = OpenAIConversationsSession(conversation_id="conv_abc123")
```

### SQLAlchemySession (Production)

```python
from agents.extensions.sqlalchemy_session import SQLAlchemySession

# URL로 생성
session = await SQLAlchemySession.from_url(
    session_id="user_123",
    url="postgresql+asyncpg://user:pass@localhost/db",
    create_tables=True,
)

# Engine으로 생성
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine("postgresql+asyncpg://...")
session = SQLAlchemySession(
    session_id="user_123",
    engine=engine,
    create_tables=True,
)
```

### AdvancedSQLiteSession (브랜칭 지원)

```python
from agents.extensions.advanced_sqlite_session import AdvancedSQLiteSession

session = AdvancedSQLiteSession(
    session_id="user_123",
    db_path="conversations.db",
)

# 특정 턴에서 브랜치 생성
branch_session = await session.create_branch_from_turn(turn_number=2)

# 사용량 추적
await session.store_run_usage(result)
```

### EncryptedSession

```python
from agents.extensions.encrypted_session import EncryptedSession

base_session = SQLiteSession(session_id="user_123", db_path="conv.db")

encrypted_session = EncryptedSession(
    session_id="user_123",
    underlying_session=base_session,
    encryption_key="your-32-byte-key-here",
    ttl=3600,  # 1시간 후 만료
)
```

### OpenAIResponsesCompactionSession (자동 압축)

```python
from agents.extensions.session import OpenAIResponsesCompactionSession

session = OpenAIResponsesCompactionSession(
    underlying_session=SQLiteSession("user_123"),
    compaction_threshold=50,  # 50개 메시지 후 압축
)

# 수동 압축
await session.run_compaction({"force": True})
```

### Session Operations

```python
# 히스토리 조회
items = await session.get_items()

# 아이템 추가
await session.add_items([new_item])

# 마지막 아이템 제거 (undo)
last_item = await session.pop_item()

# 세션 초기화
await session.clear_session()
```

---

## 7. Running Agents

### Runner Methods

```python
from agents import Agent, Runner, RunConfig

agent = Agent(name="Bot", instructions="...")

# 동기 실행
result = Runner.run_sync(agent, "Hello")

# 비동기 실행
result = await Runner.run(agent, "Hello")

# 스트리밍 실행
async with Runner.run_streamed(agent, "Hello") as stream:
    async for event in stream.stream_events():
        if event.type == "raw_response_event":
            print(event.data)
```

### RunConfig Options

```python
from agents import RunConfig, ModelSettings

config = RunConfig(
    # 모델 설정
    model="gpt-5.2",
    model_settings=ModelSettings(temperature=0.7),

    # 턴 제한
    max_turns=10,

    # Guardrails
    input_guardrails=[...],
    output_guardrails=[...],

    # Handoff 설정
    handoff_input_filter=my_filter,
    nest_handoff_history=True,

    # Tracing
    tracing_disabled=False,
    workflow_name="MyWorkflow",
    trace_id="trace_123",
    group_id="group_456",
    trace_include_sensitive_data=False,

    # Model input hook
    call_model_input_filter=my_input_filter,
)

result = await Runner.run(agent, "Hello", run_config=config)
```

### Conversation Management

```python
# 수동 관리
result1 = await Runner.run(agent, "Hello")
next_input = result1.to_input_list() + [{"role": "user", "content": "Follow up"}]
result2 = await Runner.run(agent, next_input)

# Session으로 자동 관리
session = SQLiteSession("user_123")
result1 = await Runner.run(agent, "Hello", session=session)
result2 = await Runner.run(agent, "Follow up", session=session)  # 히스토리 자동 포함

# Server-managed (OpenAI Responses API)
result1 = await Runner.run(agent, "Hello")
result2 = await Runner.run(
    agent,
    "Follow up",
    previous_response_id=result1.response_id,
)
```

### Exception Handling

```python
from agents import (
    Runner,
    MaxTurnsExceeded,
    ModelBehaviorError,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    UserError,
)

try:
    result = await Runner.run(agent, input_text, run_config=config)
except MaxTurnsExceeded:
    print("Too many turns")
except ModelBehaviorError as e:
    print(f"Model error: {e}")
except InputGuardrailTripwireTriggered:
    print("Input blocked")
except OutputGuardrailTripwireTriggered:
    print("Output blocked")
except UserError as e:
    print(f"SDK usage error: {e}")
```

---

## 8. Tracing

### Default Tracing

트레이싱은 기본적으로 활성화되어 있으며, 다음을 자동으로 캡처합니다:
- Runner 실행
- Agent 실행
- LLM 생성
- Tool 호출
- Guardrail, Handoff

### View Traces

OpenAI 대시보드에서 확인: https://platform.openai.com/traces

### Custom Traces

```python
from agents import trace, custom_span, generation_span

with trace("MyWorkflow", group_id="user_123"):
    # 커스텀 span
    with custom_span("preprocessing"):
        data = preprocess(input_data)

    # Agent 실행 (자동으로 trace에 포함)
    result = await Runner.run(agent, data)
```

### Disable Tracing

```python
# 환경 변수로
# OPENAI_AGENTS_DISABLE_TRACING=1

# RunConfig로
config = RunConfig(tracing_disabled=True)

# 전역 설정
from agents import set_tracing_disabled
set_tracing_disabled(True)
```

### Sensitive Data Protection

```python
# RunConfig로
config = RunConfig(trace_include_sensitive_data=False)

# 환경 변수로
# OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA=false
```

### Non-OpenAI Model Tracing

```python
from agents import set_tracing_export_api_key

# 다른 모델 사용 시에도 OpenAI 트레이싱 사용
set_tracing_export_api_key("sk-openai-key-for-tracing")
```

### Custom Trace Processors

```python
from agents import add_trace_processor, set_trace_processors

# 추가 프로세서
add_trace_processor(my_custom_processor)

# 프로세서 교체
set_trace_processors([my_processor])
```

### External Integrations

지원되는 플랫폼: Weights & Biases, Arize-Phoenix, MLflow, Braintrust, Pydantic Logfire, AgentOps, LangSmith, Langfuse 등 20개 이상

---

## 9. Models

### Supported Models

```python
from agents import Agent

# OpenAI (기본)
agent = Agent(name="Bot", model="gpt-4.1")  # 기본값
agent = Agent(name="Bot", model="gpt-5.2")  # 고품질

# GPT-5.x 설정
from agents import ModelSettings

agent = Agent(
    name="Bot",
    model="gpt-5.2",
    model_settings=ModelSettings(
        reasoning={"effort": "medium"},  # none, low, medium, high
    ),
)
```

### LiteLLM Integration

```bash
pip install openai-agents[litellm]
```

```python
from agents import Agent

# Claude
agent = Agent(
    name="ClaudeBot",
    model="litellm/anthropic/claude-3-5-sonnet-20240620",
)

# Gemini
agent = Agent(
    name="GeminiBot",
    model="litellm/gemini/gemini-2.5-flash-preview-04-17",
)

# Custom endpoint
agent = Agent(
    name="CustomBot",
    model="litellm/openai/my-model",
)
```

### Custom OpenAI Client

```python
from agents import set_default_openai_client
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://my-endpoint.com/v1",
    api_key="my-key",
)

set_default_openai_client(client)
```

### API Selection

```python
from agents import set_default_openai_api

# Responses API (기본, 권장)
set_default_openai_api("responses")

# Chat Completions API
set_default_openai_api("chat_completions")
```

---

## 10. Configuration Functions

```python
from agents import (
    set_default_openai_key,
    set_default_openai_client,
    set_default_openai_api,
    set_tracing_export_api_key,
    set_tracing_disabled,
    set_trace_processors,
    enable_verbose_stdout_logging,
)

# API 키 설정
set_default_openai_key("sk-...")

# 커스텀 클라이언트
set_default_openai_client(my_client)

# API 선택
set_default_openai_api("responses")  # or "chat_completions"

# 트레이싱 API 키 (다른 모델 사용 시)
set_tracing_export_api_key("sk-...")

# 트레이싱 비활성화
set_tracing_disabled(True)

# 커스텀 트레이스 프로세서
set_trace_processors([my_processor])

# 디버그 로깅
enable_verbose_stdout_logging()
```

---

## 11. Best Practices

### Agent Design
1. **명확한 instructions**: 구체적이고 명확한 시스템 프롬프트
2. **전문화된 agents**: 단일 책임 원칙 적용
3. **적절한 handoffs**: 복잡한 워크플로우는 여러 agent로 분리

### Tools
1. **명확한 docstring**: Tool 설명과 파라미터 문서화
2. **타입 힌트**: 스키마 자동 생성을 위한 타입 명시
3. **에러 처리**: 적절한 에러 메시지 반환

### Security
1. **Input guardrails**: 유해 콘텐츠 필터링
2. **Output guardrails**: PII 및 민감 정보 검출
3. **Tool guardrails**: 위험한 작업 방지

### Performance
1. **Blocking guardrails**: 비용 최적화가 필요한 경우
2. **Tool caching**: MCP 서버 tool 목록 캐싱
3. **Session 선택**: 용도에 맞는 session 타입 선택

### Debugging
1. **Tracing 활성화**: 문제 추적
2. **verbose logging**: 개발 중 디버깅
3. **Custom spans**: 중요 단계 마킹
