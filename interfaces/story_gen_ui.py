import copy
import random
import gradio as gr

from modules import palmchat
from interfaces import utils

from pingpong import PingPong
from pingpong.context import CtxLastWindowStrategy

async def next_paragraph_gen(
    action, progress,
    time, place, mood,
    name1, age1, mbti1, personality1, job1,
    name2, age2, mbti2, personality2, job2,
    name3, age3, mbti3, personality3, job3,
    name4, age4, mbti4, personality4, job4,
    chapter1_title, chapter2_title, chapter3_title, chapter4_title,
    chapter1_content
):
    cur_progress = utils.get_progress_from_md(progress)
    nxt_progress = cur_progress + 1
    
    ctx = f"""Based on the given information as follows, give me the next paragraph of the chapter1 in JSON format. Also suggest three specific actions that the characters to choose to continue the story after the next paragraph. 

Output template is as follows: ```json{{"paragraph": "paragraph", actions:["action1", action2", action3"]}}```. DO NOT output anything other than JSON values. ONLY JSON is allowed.

when: {time}
where: {place}
mood: {mood}

main character: {{
name: {name1},
job: {job1},
age: {age1},
mbti: {mbti1},
personality: {personality1} 
}}

side character1: {{
name: {name2},
job: {job2},
age: {age2},
mbti: {mbti2},
personality: {personality2} 
}}

side character2: {{
name: {name3},
job: {job3},
age: {age3},
mbti: {mbti3},
personality: {personality3} 
}}

side character3: {{
name: {name4},
job: {job4},
age: {age4},
mbti: {mbti4},
personality: {personality4} 
}}
"""

    user_input = f"""
chapter 1: {{
title: {chapter1_title},
content: {chapter1_content}
}}

chapter 2: {{
title: {chapter2_title},
content: Not determined
}}

chapter 3: {{
title: {chapter3_title},
content: Not determined
}}

chapter 4: {{
title: {chapter4_title},
content: Not determined
}}

Continue the story based on the choice "{action}"
"""

    ppm = palmchat.GradioPaLMChatPPManager()
    ppm.add_pingpong(
        PingPong(user_input, '')
    )
    prompt = utils.build_prompts(ppm)

    response_json = None
    while response_json is None:
        response_txt = await utils.get_chat_response(prompt, ctx=ctx)
        print(response_txt)

        try:
            response_json = utils.parse_first_json_code_snippet(response_txt)
        except:
             pass
        
    print(response_json)

    return (
        utils.get_progress_md(nxt_progress),
        f"""{chapter1_content}

{response_json["paragraph"]}
""",
        response_json["actions"][0],
        response_json["actions"][1],
        response_json["actions"][2]
    )