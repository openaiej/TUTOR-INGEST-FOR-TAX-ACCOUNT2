from dotenv import load_dotenv

load_dotenv()

from graph_builder import compile_tutor_graph

from agents.accounting.calculator_agent import calculator_agent as accounting_calculator_agent
from agents.accounting.classification_agent import classification_agent as accounting_classification_agent
from agents.accounting.exam_agent import exam_agent as accounting_exam_agent
from agents.accounting.feynman_agent import feynman_agent as accounting_feynman_agent
from agents.accounting.quiz_agent import quiz_agent as accounting_quiz_agent
from agents.accounting.teacher_agent import teacher_agent as accounting_teacher_agent
from agents.accounting.wrong_note_agent import wrong_note_agent as accounting_wrong_note_agent

from agents.tax.calculator_agent import calculator_agent as tax_calculator_agent
from agents.tax.classification_agent import classification_agent as tax_classification_agent
from agents.tax.exam_agent import exam_agent as tax_exam_agent
from agents.tax.feynman_agent import feynman_agent as tax_feynman_agent
from agents.tax.quiz_agent import quiz_agent as tax_quiz_agent
from agents.tax.teacher_agent import teacher_agent as tax_teacher_agent
from agents.tax.wrong_note_agent import wrong_note_agent as tax_wrong_note_agent

graph_tax = compile_tutor_graph(
    tax_classification_agent,
    tax_teacher_agent,
    tax_feynman_agent,
    tax_quiz_agent,
    tax_exam_agent,
    tax_wrong_note_agent,
    tax_calculator_agent,
)

graph_accounting = compile_tutor_graph(
    accounting_classification_agent,
    accounting_teacher_agent,
    accounting_feynman_agent,
    accounting_quiz_agent,
    accounting_exam_agent,
    accounting_wrong_note_agent,
    accounting_calculator_agent,
)

# 기본 그래프 (전산세무 2급)
graph = graph_tax

GRAPHS_BY_COURSE = {
    "tax": graph_tax,
    "accounting": graph_accounting,
}
