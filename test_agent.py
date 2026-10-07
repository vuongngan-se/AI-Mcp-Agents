import asyncio
from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams

# 1. Khai báo ứng dụng MCPApp
app = MCPApp(name="my_first_agent")


async def main():
    async with app.run():
        # 2. Khởi tạo Agent với tên và chỉ dẫn
        agent = Agent(
            name="assistant",
            instruction="Bạn là một trợ lý AI hữu ích.",
        )

        async with agent:
            # 3. Gắn LLM (dùng OpenAI API tương thích qua 9router)
            llm = await agent.attach_llm(OpenAIAugmentedLLM)

            # 4. Gửi yêu cầu cho LLM chỉ định model gemini-3.6-flash
            response = await llm.generate_str(
                "Xin chào! Hãy giới thiệu ngắn gọn 2 câu về bản thân.",
                request_params=RequestParams(model="gemini-3.6-flash"),
            )
            print("\n🤖 KẾT QUẢ FROM AGENT:")
            print(response)


if __name__ == "__main__":
    asyncio.run(main())
