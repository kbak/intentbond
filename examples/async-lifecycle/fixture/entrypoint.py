# [impl->req~form-wire~1]
# [impl->req~form-nonblank~1]
# [impl->req~form-label~2]
# [impl->req~form-async~1]
import asyncio

from client.component import render
from client.controller import Form
from client.labels import LABEL
from schema import payload
from server import validate


def evaluate(case):
    form = Form()
    if "async" not in case:
        return {
            "component": render(LABEL),
            "payload": payload(case["value"]),
            "response": form.submit(case["value"]),
        }

    async def sequence():
        tasks = []
        for item in case["async"]:

            async def request(data, delay=item["delay"]):
                await asyncio.sleep(delay)
                return validate(data)

            tasks.append(asyncio.create_task(form.validate(item["value"], request)))
            await asyncio.sleep(0)
        await asyncio.gather(*tasks)

    asyncio.run(sequence())
    return {"error": form.error, "pending": form.pending, "component": render(LABEL)}
