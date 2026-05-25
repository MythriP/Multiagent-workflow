---
description: Run the script_agent pipeline against a topic.json to produce a rendered video.
argument-hint: <topic.json path> [--resume narrative|scenes|render]
---

Generate a full video from the given topic.

1. Validate the topic path exists. If not, ask the user for the correct path.
2. Run `python -m script_agent.run --topic $ARGUMENTS`.
3. Stream the log; on completion, locate the output folder under `script_agent/outputs/$(date +%Y-%m-%d)/` and report:
   - path to `final.mp4`
   - path to `narrative.txt`
   - path to `video_script.json`
   - any critique iterations from `narrative_critique.txt`
4. If any step failed, surface the last 30 lines of the log and the path to the full log file.
