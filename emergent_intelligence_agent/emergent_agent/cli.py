"""CLI demo for the emergent agent framework."""

from __future__ import annotations

import argparse

from .core import EmergentAgent
from .evaluation import EvalCase, Evaluator
from .evolution import EvolutionaryOptimizer


def build_demo_agent() -> EmergentAgent:
    agent = EmergentAgent()
    agent.knowledge.add(
        "architecture",
        "A safe emergent agent should separate safety, language processing, reasoning, data skills, evaluation, and evolution.",
    )
    agent.knowledge.add(
        "evolution",
        "Evolution should optimize inspectable configuration first and stop after plateau. Fitness should include usefulness, grounding, and safety.",
    )
    agent.knowledge.add(
        "reasoning",
        "Reasoning improves when tasks are decomposed, checked, and synthesized with retrieved evidence.",
    )
    return agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the emergent agent prototype.")
    parser.add_argument("prompt", nargs="*", help="Prompt to answer")
    parser.add_argument("--evolve", action="store_true", help="Run local evolutionary optimization first")
    args = parser.parse_args()

    agent = build_demo_agent()

    if args.evolve:
        evaluator = Evaluator(
            [
                EvalCase("Design a safe emergent agent", ("safety", "reasoning", "evaluation")),
                EvalCase("How should evolution work?", ("fitness", "plateau", "tests")),
                EvalCase("Explain emergent intelligence", ("modules", "feedback", "evaluation")),
            ]
        )
        agent, records = EvolutionaryOptimizer().evolve(agent, evaluator)
        print("Evolution records:")
        for record in records:
            print(f"gen={record.generation} best={record.best_score:.2f} mean={record.mean_score:.2f} name={record.best_name}")
        print()

    prompt = " ".join(args.prompt) or "Design a safe emergent intelligence agent framework"
    response = agent.answer(prompt)
    print(response.answer)
    print("\nTrace summary:")
    for step in response.trace.plan:
        print(f"- {step}")


if __name__ == "__main__":
    main()
