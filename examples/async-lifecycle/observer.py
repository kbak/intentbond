"""Observe real Form requests with futures; never read implementation generation IDs."""

import asyncio

from contract import validate


def observe(case):
    events = case["events"]
    validate(events)
    from client.component import render
    from client.controller import Form
    from client.labels import LABEL
    from server import validate as server_validate

    async def sequence():
        form = Form()
        gates = []
        tasks = []
        requests = []
        states = []
        try:
            for event in events:
                if "start" in event:
                    index = len(tasks)
                    gate = asyncio.get_running_loop().create_future()
                    gates.append(gate)
                    requests.append(None)

                    async def request(data, gate=gate, index=index):
                        requests[index] = dict(data)
                        await gate
                        return server_validate(data)

                    tasks.append(asyncio.create_task(form.validate(event["start"], request)))
                    await asyncio.sleep(0)
                    name = f"start:{index}"
                else:
                    index = event["complete"]
                    gates[index].set_result(None)
                    await tasks[index]
                    name = f"complete:{index}"
                states.append({"event": name, "error": form.error, "pending": form.pending})
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return {"component": render(LABEL), "requests": requests, "states": states}

    return asyncio.run(sequence())
