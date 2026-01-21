# Google Agent Development Kit (ADK) Complete Reference

> **최신 정보 필요 시**: Context7 MCP를 통해 조회 (Library ID: `/google/adk-docs`)

## Overview

Google ADK는 AI 에이전트를 구축, 평가, 배포하기 위한 유연한 프레임워크입니다.

### Core Features
- **LLM Agents**: 동적 추론 및 도구 사용
- **Workflow Agents**: Sequential, Parallel, Loop 패턴
- **Multi-Agent Systems**: 계층적 에이전트 구성
- **Rich Tool Ecosystem**: 내장 도구 및 커스텀 도구
- **Callbacks**: 라이프사이클 이벤트 훅
- **Deployment**: Vertex AI, Cloud Run, GKE, Docker

### Supported Languages
- Python 3.10+
- TypeScript/JavaScript
- Go
- Java 17+

### Installation

```bash
# Python
pip install google-adk

# TypeScript
npm install @google/adk @google/adk-devtools

# Java (Maven)
<dependency>
    <groupId>com.google.cloud</groupId>
    <artifactId>google-adk</artifactId>
</dependency>
```

---

## 1. LLM Agents

### Basic Agent Creation

```python
from google.adk import Agent

agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    description="A helpful assistant",
    instruction="You are a helpful assistant that answers questions.",
)
```

### Agent Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Agent 식별자 (필수, multi-agent에서 중요) |
| `model` | `str` | LLM 모델 (예: "gemini-2.0-flash", "gemini-2.5-pro") |
| `description` | `str` | Agent 능력 요약 (다른 agent가 라우팅에 사용) |
| `instruction` | `str` | 시스템 프롬프트 (동적 템플릿 지원: `{var}`) |
| `tools` | `list` | 사용 가능한 도구 목록 |
| `sub_agents` | `list` | 하위 에이전트 목록 |
| `input_schema` | `type` | 입력 스키마 정의 |
| `output_schema` | `type` | 출력 스키마 정의 (JSON 강제) |
| `output_key` | `str` | 최종 응답을 저장할 state 키 |
| `include_contents` | `str` | 히스토리 포함 여부 ('default' \| 'none') |
| `generate_content_config` | `dict` | temperature, max_tokens 등 |
| `planner` | `Planner` | 멀티스텝 추론 플래너 |
| `code_executor` | `CodeExecutor` | 코드 실행기 |

### Dynamic Instructions

```python
agent = Agent(
    name="personalized",
    model="gemini-2.0-flash",
    instruction="""
    You are helping {user_name}.
    Their preferences: {artifact.user_prefs}
    Current date: {current_date}
    """,
)
```

### Structured Output

```python
from pydantic import BaseModel

class WeatherResponse(BaseModel):
    city: str
    temperature: float
    condition: str

agent = Agent(
    name="weather_agent",
    model="gemini-2.0-flash",
    instruction="Extract weather information",
    output_schema=WeatherResponse,  # JSON 출력 강제
)
```

### Generation Config

```python
agent = Agent(
    name="creative_agent",
    model="gemini-2.0-flash",
    generate_content_config={
        "temperature": 0.9,
        "max_output_tokens": 2048,
        "top_p": 0.95,
        "top_k": 40,
    },
)
```

---

## 2. Workflow Agents

### 2.1 SequentialAgent

순차적으로 sub-agent 실행. 각 agent의 출력이 다음 agent의 context에 포함.

```python
from google.adk import SequentialAgent, Agent

# Step agents
data_fetcher = Agent(
    name="data_fetcher",
    model="gemini-2.0-flash",
    instruction="Fetch relevant data",
    output_key="fetched_data",  # state에 저장
)

analyzer = Agent(
    name="analyzer",
    model="gemini-2.0-flash",
    instruction="Analyze the data: {fetched_data}",  # 이전 출력 참조
    output_key="analysis",
)

reporter = Agent(
    name="reporter",
    model="gemini-2.0-flash",
    instruction="Generate report from analysis: {analysis}",
)

# Pipeline
pipeline = SequentialAgent(
    name="data_pipeline",
    sub_agents=[data_fetcher, analyzer, reporter],
)
```

### 2.2 ParallelAgent

동시에 여러 sub-agent 실행. 모든 agent가 동일한 `session.state` 공유.

```python
from google.adk import ParallelAgent, Agent

web_searcher = Agent(
    name="web_searcher",
    model="gemini-2.0-flash",
    instruction="Search the web for information",
    output_key="web_results",
)

doc_searcher = Agent(
    name="doc_searcher",
    model="gemini-2.0-flash",
    instruction="Search internal documents",
    output_key="doc_results",
)

db_searcher = Agent(
    name="db_searcher",
    model="gemini-2.0-flash",
    instruction="Query the database",
    output_key="db_results",
)

# Parallel execution
parallel_search = ParallelAgent(
    name="parallel_search",
    sub_agents=[web_searcher, doc_searcher, db_searcher],
)

# Aggregator (after parallel)
aggregator = Agent(
    name="aggregator",
    model="gemini-2.0-flash",
    instruction="""
    Combine results from all sources:
    - Web: {web_results}
    - Docs: {doc_results}
    - DB: {db_results}
    """,
)

# Full pipeline
full_pipeline = SequentialAgent(
    name="search_pipeline",
    sub_agents=[parallel_search, aggregator],
)
```

### 2.3 LoopAgent

조건 충족 또는 최대 반복까지 반복 실행.

```python
from google.adk import LoopAgent, Agent

refiner = Agent(
    name="refiner",
    model="gemini-2.0-flash",
    instruction="""
    Review and improve the content.
    If satisfied, respond with escalate=True.
    Current content: {draft}
    """,
    output_key="draft",
)

# Loop until satisfied or max iterations
refinement_loop = LoopAgent(
    name="refinement_loop",
    sub_agent=refiner,
    max_iterations=5,
)
```

---

## 3. Tools

### 3.1 Function Tools

Python 함수를 자동으로 tool로 변환. 타입 힌트와 docstring으로 스키마 생성.

```python
from google.adk import Agent

def get_weather(city: str, unit: str = "celsius") -> dict:
    """Get weather information for a city.

    Args:
        city: The city name to get weather for
        unit: Temperature unit (celsius or fahrenheit)

    Returns:
        Weather information including temperature and conditions
    """
    # Implementation
    return {
        "status": "success",
        "city": city,
        "temperature": 22,
        "unit": unit,
        "condition": "sunny",
    }

def search_database(query: str, limit: int = 10) -> dict:
    """Search the database for relevant records.

    Args:
        query: Search query string
        limit: Maximum number of results

    Returns:
        List of matching records
    """
    return {
        "status": "success",
        "results": [...],
        "count": 5,
    }

agent = Agent(
    name="tool_agent",
    model="gemini-2.0-flash",
    instruction="Help users with weather and database queries",
    tools=[get_weather, search_database],
)
```

### Required vs Optional Parameters

```python
# Required parameters (no default)
def required_params(city: str, date: str) -> dict:
    """Both city and date are required."""
    pass

# Optional parameters (with default or Optional type)
from typing import Optional

def optional_params(
    city: str,                    # Required
    date: str = "today",          # Optional with default
    unit: Optional[str] = None,   # Optional, can be None
) -> dict:
    pass
```

### Return Type Best Practices

```python
def good_tool_response(query: str) -> dict:
    """Always include status in response."""
    try:
        result = process(query)
        return {
            "status": "success",
            "data": result,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }
```

### 3.2 Built-in Tools

#### Google Search

```python
from google.adk.tools import GoogleSearchTool

agent = Agent(
    name="search_agent",
    model="gemini-2.0-flash",
    tools=[GoogleSearchTool()],
)
```

#### Code Execution

```python
from google.adk.tools import CodeExecutionTool

agent = Agent(
    name="code_agent",
    model="gemini-2.0-flash",
    tools=[CodeExecutionTool()],
)
```

### 3.3 AgentTool (Agent as Tool)

다른 agent를 tool로 사용.

```python
from google.adk import Agent, AgentTool

specialist = Agent(
    name="data_specialist",
    model="gemini-2.0-flash",
    instruction="You are a data analysis expert",
)

# Wrap as tool
specialist_tool = AgentTool(agent=specialist)

main_agent = Agent(
    name="coordinator",
    model="gemini-2.0-flash",
    instruction="Coordinate tasks and delegate to specialists",
    tools=[specialist_tool],
)
```

### 3.4 MCP Tools

```python
from google.adk.tools import MCPTool

mcp_tool = MCPTool(
    server_url="https://mcp.example.com",
    tool_name="my_tool",
)

agent = Agent(
    name="mcp_agent",
    model="gemini-2.0-flash",
    tools=[mcp_tool],
)
```

### 3.5 OpenAPI Tools

```python
from google.adk.tools import OpenAPITool

api_tool = OpenAPITool(
    spec_url="https://api.example.com/openapi.json",
)

agent = Agent(
    name="api_agent",
    model="gemini-2.0-flash",
    tools=[api_tool],
)
```

### 3.6 Long-Running Tools

비동기 작업을 위한 특수 도구.

```python
from google.adk.tools import LongRunningFunctionTool

class DataProcessingTool(LongRunningFunctionTool):
    def initiate(self, data: str) -> dict:
        """Start the long-running operation."""
        operation_id = start_async_processing(data)
        return {
            "status": "pending",
            "operation_id": operation_id,
        }

    def check_status(self, operation_id: str) -> dict:
        """Check operation status."""
        status = get_operation_status(operation_id)
        if status.complete:
            return {
                "status": "success",
                "result": status.result,
            }
        return {
            "status": "pending",
            "progress": status.progress,
        }
```

---

## 4. Callbacks

### Callback Types

| Callback | 시점 | 용도 |
|----------|------|------|
| `before_agent_callback` | Agent 처리 전 | 전체 실행 래핑 |
| `after_agent_callback` | Agent 완료 후 | 최종 출력 수정 |
| `before_model_callback` | LLM 호출 전 | 요청 검사/수정, guardrails |
| `after_model_callback` | LLM 응답 후 | 응답 정제/변환 |
| `before_tool_callback` | Tool 실행 전 | 인자 검증, 정책 적용 |
| `after_tool_callback` | Tool 실행 후 | 결과 후처리 |

### Return Value Control

- **`None` 반환**: 기본 동작 진행
- **값 반환**: 기본 동작 대체 (해당 단계 스킵)

### Callback Examples

```python
from google.adk import Agent, CallbackContext
from google.genai.types import Content, LlmResponse

# Before Model: Input validation / Guardrails
def before_model_guardrail(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> LlmResponse | None:
    """Block harmful content before LLM call."""
    user_input = str(llm_request.contents[-1])

    if "forbidden_topic" in user_input.lower():
        # Return response to skip LLM call
        return LlmResponse(
            content=Content(
                parts=[Part(text="I cannot discuss that topic.")]
            )
        )

    # Return None to proceed normally
    return None

# After Model: Response sanitization
def after_model_sanitize(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse | None:
    """Sanitize sensitive information from response."""
    response_text = str(llm_response.content)

    # Remove PII
    sanitized = remove_pii(response_text)

    if sanitized != response_text:
        return LlmResponse(
            content=Content(parts=[Part(text=sanitized)])
        )

    return None  # Use original

# Before Tool: Argument validation
def before_tool_validate(
    callback_context: CallbackContext,
    tool_name: str,
    tool_args: dict,
) -> dict | None:
    """Validate tool arguments."""
    if tool_name == "database_query":
        if "DROP" in tool_args.get("query", "").upper():
            return {"status": "error", "message": "Dangerous query blocked"}

    return None  # Proceed with tool execution

# After Tool: Result logging
def after_tool_log(
    callback_context: CallbackContext,
    tool_name: str,
    tool_result: dict,
) -> dict | None:
    """Log tool execution results."""
    print(f"Tool {tool_name} returned: {tool_result}")
    return None  # Use original result

# Register callbacks
agent = Agent(
    name="safe_agent",
    model="gemini-2.0-flash",
    instruction="You are a helpful assistant",
    before_model_callback=before_model_guardrail,
    after_model_callback=after_model_sanitize,
    before_tool_callback=before_tool_validate,
    after_tool_callback=after_tool_log,
)
```

### Callback Context

```python
def my_callback(callback_context: CallbackContext, ...):
    # Agent 정보
    agent_name = callback_context.agent_name

    # Session state 접근
    user_id = callback_context.state.get("user_id")

    # State 업데이트
    callback_context.state["last_action"] = "callback_executed"
```

---

## 5. Multi-Agent Systems

### Communication Patterns

#### 1. Shared Session State

```python
agent1 = Agent(
    name="researcher",
    model="gemini-2.0-flash",
    instruction="Research the topic and save findings",
    output_key="research_findings",  # 자동으로 state에 저장
)

agent2 = Agent(
    name="writer",
    model="gemini-2.0-flash",
    instruction="Write article based on: {research_findings}",  # state에서 읽기
)

pipeline = SequentialAgent(
    name="content_pipeline",
    sub_agents=[agent1, agent2],
)
```

#### 2. LLM-Driven Delegation (Transfer)

```python
support_agent = Agent(
    name="support",
    model="gemini-2.0-flash",
    description="Handles technical support questions",
    instruction="You handle technical support",
)

billing_agent = Agent(
    name="billing",
    model="gemini-2.0-flash",
    description="Handles billing and payment questions",
    instruction="You handle billing inquiries",
)

# Router가 자동으로 transfer_to_agent 호출 가능
router = Agent(
    name="router",
    model="gemini-2.0-flash",
    instruction="Route user to appropriate department",
    sub_agents=[support_agent, billing_agent],
)
```

#### 3. Explicit AgentTool

```python
from google.adk import AgentTool

specialist = Agent(
    name="specialist",
    model="gemini-2.0-flash",
    instruction="You are an expert analyst",
)

coordinator = Agent(
    name="coordinator",
    model="gemini-2.0-flash",
    instruction="Coordinate work and use specialist when needed",
    tools=[AgentTool(agent=specialist)],
)
```

### Multi-Agent Patterns

#### Coordinator/Dispatcher

```python
specialists = [
    Agent(name="finance", description="Financial analysis", ...),
    Agent(name="legal", description="Legal questions", ...),
    Agent(name="tech", description="Technical support", ...),
]

coordinator = Agent(
    name="coordinator",
    model="gemini-2.0-flash",
    instruction="Route requests to appropriate specialist",
    sub_agents=specialists,
)
```

#### Sequential Pipeline

```python
pipeline = SequentialAgent(
    name="document_pipeline",
    sub_agents=[
        Agent(name="extractor", instruction="Extract key info", output_key="extracted"),
        Agent(name="analyzer", instruction="Analyze: {extracted}", output_key="analysis"),
        Agent(name="summarizer", instruction="Summarize: {analysis}"),
    ],
)
```

#### Parallel Fan-Out/Gather

```python
parallel_research = ParallelAgent(
    name="parallel_research",
    sub_agents=[
        Agent(name="web", output_key="web_data", ...),
        Agent(name="db", output_key="db_data", ...),
        Agent(name="api", output_key="api_data", ...),
    ],
)

gatherer = Agent(
    name="gatherer",
    instruction="Combine: {web_data}, {db_data}, {api_data}",
)

full_pipeline = SequentialAgent(
    name="research_pipeline",
    sub_agents=[parallel_research, gatherer],
)
```

#### Generator-Critic Loop

```python
generator = Agent(
    name="generator",
    instruction="Generate content based on requirements",
    output_key="draft",
)

critic = Agent(
    name="critic",
    instruction="""
    Review the draft: {draft}
    If acceptable, respond with escalate=True.
    Otherwise, provide specific feedback.
    """,
    output_key="feedback",
)

refinement = LoopAgent(
    name="refinement",
    sub_agent=SequentialAgent(
        name="gen_crit",
        sub_agents=[generator, critic],
    ),
    max_iterations=3,
)
```

---

## 6. Sessions & State

### Session Management

```python
from google.adk import Agent
from google.adk.sessions import InMemorySessionService

# Session service 생성
session_service = InMemorySessionService()

# Session 생성
session = session_service.create_session(
    app_name="my_app",
    user_id="user_123",
)

# Agent 실행 with session
runner = Runner(agent=agent, session_service=session_service)
response = await runner.run(
    session_id=session.id,
    user_input="Hello",
)
```

### State Management

```python
# State 접근 (callback 또는 tool 내에서)
def my_tool(ctx: ToolContext) -> dict:
    # State 읽기
    user_prefs = ctx.session.state.get("user_preferences", {})

    # State 업데이트
    ctx.session.state["last_query"] = "my_tool called"

    # Temporary state (현재 invocation만)
    ctx.session.state["temp:intermediate_result"] = "..."

    return {"status": "success"}
```

### Session Service Options

- **InMemorySessionService**: 개발/테스트용 (재시작 시 데이터 손실)
- **Cloud-based services**: 프로덕션용 영구 저장

---

## 7. Running Agents

### CLI Commands

```bash
# Dev UI (브라우저 기반)
adk web

# Terminal 실행
adk run agent.py

# API Server
adk api_server --port 8080
```

### Programmatic Execution

```python
from google.adk import Agent, Runner

agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    instruction="You are helpful",
)

# Runner 생성
runner = Runner(agent=agent)

# 동기 실행
response = runner.run_sync(user_input="Hello")
print(response.content)

# 비동기 실행
response = await runner.run(user_input="Hello")

# 스트리밍
async for chunk in runner.run_stream(user_input="Hello"):
    print(chunk.content, end="")
```

### With Session

```python
from google.adk.sessions import InMemorySessionService

session_service = InMemorySessionService()
session = session_service.create_session(
    app_name="my_app",
    user_id="user_123",
)

runner = Runner(agent=agent, session_service=session_service)

# 첫 번째 메시지
response1 = await runner.run(
    session_id=session.id,
    user_input="My name is John",
)

# 두 번째 메시지 (히스토리 유지)
response2 = await runner.run(
    session_id=session.id,
    user_input="What's my name?",
)
```

---

## 8. Deployment

### Vertex AI Agent Engine

```bash
# Deploy to Vertex AI
adk deploy vertex-ai \
    --project=my-project \
    --region=us-central1 \
    --agent=agent.py
```

### Cloud Run

```bash
# Deploy to Cloud Run
adk deploy cloud-run \
    --project=my-project \
    --region=us-central1
```

### Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["adk", "api_server", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
# Build and run
docker build -t my-agent .
docker run -p 8080:8080 my-agent
```

### Environment Variables

```bash
# Google AI Studio
export GOOGLE_API_KEY=your_api_key

# Vertex AI
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=your_project
export GOOGLE_CLOUD_REGION=us-central1
```

---

## 9. Authentication

### Google AI Studio

```python
# .env 파일
GOOGLE_API_KEY=your_api_key
```

### Vertex AI

```python
# .env 파일
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your_project
GOOGLE_CLOUD_REGION=us-central1

# Application Default Credentials 설정
# gcloud auth application-default login
```

---

## 10. Best Practices

### Agent Design

1. **명확한 instruction**: 구체적이고 명확한 지시
2. **적절한 description**: 다른 agent가 라우팅에 사용
3. **output_key 활용**: multi-agent 간 데이터 전달
4. **적절한 agent 타입 선택**: LLM vs Workflow

### Tools

1. **명확한 docstring**: LLM이 tool 사용법 이해
2. **타입 힌트**: 스키마 자동 생성
3. **status 포함**: 응답에 항상 status 필드
4. **에러 처리**: 명확한 에러 메시지

### Multi-Agent

1. **단일 책임**: 각 agent는 하나의 역할
2. **명확한 계층**: parent-child 관계 명확히
3. **state 활용**: output_key로 데이터 전달
4. **적절한 패턴 선택**: Sequential, Parallel, Loop

### Callbacks

1. **Guardrails**: before_model_callback으로 입력 검증
2. **Sanitization**: after_model_callback으로 출력 정제
3. **Logging**: after_tool_callback으로 실행 로깅
4. **None 반환**: 기본 동작 유지 시

### Performance

1. **ParallelAgent**: 독립 작업은 병렬 실행
2. **캐싱**: 반복 요청 캐싱
3. **적절한 모델**: 작업에 맞는 모델 선택

### Security

1. **Input validation**: callback으로 입력 검증
2. **Output sanitization**: PII 제거
3. **Tool guardrails**: 위험한 작업 방지
4. **Environment variables**: API 키 안전 관리
