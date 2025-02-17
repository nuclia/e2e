import asyncio

from nuclia.lib.langchain import NucliaNuaChat
from langchain_core.messages import HumanMessage

TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImtpZCI6Im51YSJ9.eyJpc3MiOiJodHRwczovL2V1cm9wZS0xLnN0YXNoaWZ5LmNsb3VkLyIsImlhdCI6MTcwMzQzNjE1Mywic3ViIjoiODBhNWU1MzAtOGU1OC00YmY0LWE5Y2MtNmFiOTVjZDRiMmIzIiwianRpIjoiNDgyNzM1N2ItZjhhOS00Njc0LTkxZjUtYzY2NjA1M2Q1NTYyIiwiZXhwIjoyNTMzNzA3NjQ4MDAsImtleSI6ImMxMGQ0NTE5LWI1YTUtNGQ3Zi04YWQxLTRiZjY1NjkwZjFiZiIsImFsbG93X2tiX21hbmFnZW1lbnQiOmZhbHNlfQ.4SCi3Ec4rgMRBsTUeovqnwS-_6jrlRuoMSSwA1akg_8wbsT0LGJzglBZnyjMYul5HY1wContP0dXsopkkNjeVm5KvmoXXvrjKwA1W8GKqpYOwLGM1qZVPyrtX416D_DS0z64alNBf89zp3MyBvbXFlirwvcCbSxiErofN3jemwnHfUXYTUln5OGRoRN1SroQ0kknj_unrmTGoI77Mo9JuIUzYUVZhUBc1kxM7iWJJeTjJeP7x8YTk6xWswI4Sg0SooC0_IjodgPLnQ6Th3t6VGTMP91bYBqYRc4g37Qya73bNAJMrHI3a5AqH1oPbu6JgAgofJIeLQfd7-bYgfowTjZjN2jaBSF9C-fWwWKeRhRdi1tvNpFbB9cXXuvQz9JLtFIiN1cgovdfL3JprpESO24pslUjkD5se8mw64VSKjJHvlRK6HMlz-czAJctks7bNUeNLxfXbe6TnRza7sX7y3AZfA8Ig1aDX2FwInOV6zxRx23zyNSWXKvwGLUFsp3-f0YnwLkYUyd4cNnuj38W_JTML2kSDSpPvcPhK7HhBkV6PBgSv1DNGisVxERAKUHYMFX7EqLHnLxR89BmrtZOxuizHq2lyjW1u2MPNjbwaTnc-ydVKWCNtYtlVGpnb47vdm8DaAgF5S59uLr4WmX4krg2n9lbzBZLH2LapshVRFg"


if __name__ == "__main__":
    model = NucliaNuaChat(
        model_name="chatgpt-azure-4o",
        token=TOKEN,
    )

    print()
    print("> test sync call")
    answer = model.invoke([HumanMessage(content="Who is Eudald?")])
    print(answer.content)

    print()
    print("> test sync streaming")
    for chunk in model.stream([HumanMessage(content="Who is the CEO of Nuclia?")]):
        print(chunk.content, end="", flush=True)

    async def run_async():
        print()
        print("> test async call")

        answer2 = await model.ainvoke(
            [HumanMessage(content="What is the capital of catalonia")]
        )
        print(answer2.content)

        print()
        print("> test async streaming")

        async for chunk in model.astream(
            [HumanMessage(content="What are the capitals of provinces in spain")]
        ):
            print(chunk.content, end="", flush=True)

    asyncio.run(run_async())
