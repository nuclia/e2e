import sys
from crewai import Agent, Task
import os
from dotenv import load_dotenv
from crewai import Crew, Process

from nuclia.lib.langchain import NucliaNuaChat

load_dotenv()


TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImtpZCI6Im51YSJ9.eyJpc3MiOiJodHRwczovL2V1cm9wZS0xLnN0YXNoaWZ5LmNsb3VkLyIsImlhdCI6MTcwMzQzNjE1Mywic3ViIjoiODBhNWU1MzAtOGU1OC00YmY0LWE5Y2MtNmFiOTVjZDRiMmIzIiwianRpIjoiNDgyNzM1N2ItZjhhOS00Njc0LTkxZjUtYzY2NjA1M2Q1NTYyIiwiZXhwIjoyNTMzNzA3NjQ4MDAsImtleSI6ImMxMGQ0NTE5LWI1YTUtNGQ3Zi04YWQxLTRiZjY1NjkwZjFiZiIsImFsbG93X2tiX21hbmFnZW1lbnQiOmZhbHNlfQ.4SCi3Ec4rgMRBsTUeovqnwS-_6jrlRuoMSSwA1akg_8wbsT0LGJzglBZnyjMYul5HY1wContP0dXsopkkNjeVm5KvmoXXvrjKwA1W8GKqpYOwLGM1qZVPyrtX416D_DS0z64alNBf89zp3MyBvbXFlirwvcCbSxiErofN3jemwnHfUXYTUln5OGRoRN1SroQ0kknj_unrmTGoI77Mo9JuIUzYUVZhUBc1kxM7iWJJeTjJeP7x8YTk6xWswI4Sg0SooC0_IjodgPLnQ6Th3t6VGTMP91bYBqYRc4g37Qya73bNAJMrHI3a5AqH1oPbu6JgAgofJIeLQfd7-bYgfowTjZjN2jaBSF9C-fWwWKeRhRdi1tvNpFbB9cXXuvQz9JLtFIiN1cgovdfL3JprpESO24pslUjkD5se8mw64VSKjJHvlRK6HMlz-czAJctks7bNUeNLxfXbe6TnRza7sX7y3AZfA8Ig1aDX2FwInOV6zxRx23zyNSWXKvwGLUFsp3-f0YnwLkYUyd4cNnuj38W_JTML2kSDSpPvcPhK7HhBkV6PBgSv1DNGisVxERAKUHYMFX7EqLHnLxR89BmrtZOxuizHq2lyjW1u2MPNjbwaTnc-ydVKWCNtYtlVGpnb47vdm8DaAgF5S59uLr4WmX4krg2n9lbzBZLH2LapshVRFg"

default_llm = NucliaNuaChat(
    model_name="chatgpt-azure-4o",
    token=TOKEN,
)


# Create a researcher agent
researcher = Agent(
    role="Senior Researcher",
    goal="Discover groundbreaking technologies",
    verbose=True,
    llm=default_llm,
    backstory="A curious mind fascinated by cutting-edge innovation and the potential to change the world, you know everything about tech.",
)

# # Task for the researcher
# research_task = Task(
#     description="Identify the next big trend in AI",
#     expected_output="5 paragraphs on the next big AI trend",
#     agent=researcher,  # Assigning the task to the researcher
# )


# # Instantiate your crew
# tech_crew = Crew(
#     agents=[researcher],
#     tasks=[research_task],
#     process=Process.sequential,  # Tasks will be executed one after the other
# )

# # # Begin the task execution
# # tech_crew.kickoff()
