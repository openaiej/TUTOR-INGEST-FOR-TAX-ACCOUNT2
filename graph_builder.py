"""코스(세무/회계)별 동일 토폴로지의 튜터 그래프를 컴파일합니다."""

from langgraph.graph import END, START, MessagesState, StateGraph


class TutorState(MessagesState):
    current_agent: str


def router_check(state: TutorState):
    return state.get("current_agent", "classification_agent")


def compile_tutor_graph(
    classification_agent,
    teacher_agent,
    feynman_agent,
    quiz_agent,
    exam_agent,
    wrong_note_agent,
    calculator_agent,
):
    graph_builder = StateGraph(TutorState)

    graph_builder.add_node(
        "classification_agent",
        classification_agent,
        destinations=(
            "teacher_agent",
            "feynman_agent",
            "quiz_agent",
            "exam_agent",
            "wrong_note_agent",
            "calculator_agent",
        ),
    )
    graph_builder.add_node("teacher_agent", teacher_agent)
    graph_builder.add_node("feynman_agent", feynman_agent)
    graph_builder.add_node("quiz_agent", quiz_agent)
    graph_builder.add_node("exam_agent", exam_agent)
    graph_builder.add_node("wrong_note_agent", wrong_note_agent)
    graph_builder.add_node("calculator_agent", calculator_agent)

    graph_builder.add_conditional_edges(
        START,
        router_check,
        [
            "classification_agent",
            "teacher_agent",
            "feynman_agent",
            "quiz_agent",
            "exam_agent",
            "wrong_note_agent",
            "calculator_agent",
        ],
    )

    graph_builder.add_edge("classification_agent", END)
    graph_builder.add_edge("teacher_agent", END)
    graph_builder.add_edge("feynman_agent", END)
    graph_builder.add_edge("quiz_agent", END)
    graph_builder.add_edge("exam_agent", END)
    graph_builder.add_edge("wrong_note_agent", END)
    graph_builder.add_edge("calculator_agent", END)

    return graph_builder.compile()
