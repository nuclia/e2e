from nuclia_e2e.tests.nua.test_da_tasks import LLM_GRAPH_OPERATION_IDENT
from nuclia_e2e.tests.nua.test_da_tasks import validate_llm_graph_output
from nucliadb_protos.writer_pb2 import BrokerMessage

import pytest


@pytest.fixture
def graph_message() -> BrokerMessage:
    message = BrokerMessage()
    message.field_metadata.add().metadata.metadata.entities[LLM_GRAPH_OPERATION_IDENT].SetInParent()
    return message


@pytest.mark.parametrize("labels", [["PLAINTIFF", "CONTRACT"], ["CONTRACT", "PLAINTIFF"]])
def test_validate_graph_output_accepts_any_entity_order(graph_message: BrokerMessage, labels: list[str]):
    entities = graph_message.field_metadata[0].metadata.metadata.entities[LLM_GRAPH_OPERATION_IDENT].entities
    for label in labels:
        entities.add(label=label)

    validate_llm_graph_output(graph_message)


@pytest.mark.parametrize("labels", [[], ["CONTRACT"], ["DEFENDANT", "CONTRACT"]])
def test_validate_graph_output_requires_plaintiff(graph_message: BrokerMessage, labels: list[str]):
    entities = graph_message.field_metadata[0].metadata.metadata.entities[LLM_GRAPH_OPERATION_IDENT].entities
    for label in labels:
        entities.add(label=label)

    with pytest.raises(AssertionError, match="Expected a PLAINTIFF entity"):
        validate_llm_graph_output(graph_message)


def test_validate_graph_output_requires_operation(graph_message: BrokerMessage):
    del graph_message.field_metadata[0].metadata.metadata.entities[LLM_GRAPH_OPERATION_IDENT]

    with pytest.raises(AssertionError):
        validate_llm_graph_output(graph_message)
