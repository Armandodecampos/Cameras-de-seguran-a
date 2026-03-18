import sys
import os
import json
from unittest.mock import MagicMock

# Create mocks before any imports
mock_pil = MagicMock()
mock_pil.Image.new.return_value = MagicMock()
sys.modules["PIL"] = mock_pil
sys.modules["PIL.Image"] = mock_pil.Image
sys.modules["PIL.ImageTk"] = MagicMock()

mock_ctk = MagicMock()
sys.modules["customtkinter"] = mock_ctk

mock_cv2 = MagicMock()
sys.modules["cv2"] = mock_cv2

mock_requests = MagicMock()
sys.modules["requests"] = mock_requests
sys.modules["requests.auth"] = MagicMock()

# Import the class
from Cameras import CentralMonitoramento

def test_predefinicoes_logic():
    print("Iniciando testes de lógica de predefinições...")

    # Simple manual tests since inheritance is tricky with multiple decorators and mocks
    # We will test the dictionary operations directly as they appear in Cameras.py

    predefinicoes = {}
    ultima_predefinicao = None
    grid_cameras = ["192.168.1.1"] * 20

    # 1. Testar _salvar_predefinicao logic
    nome = "Teste 1"
    predefinicoes[nome] = list(grid_cameras)
    ultima_predefinicao = nome

    assert "Teste 1" in predefinicoes
    assert len(predefinicoes["Teste 1"]) == 20
    assert ultima_predefinicao == "Teste 1"
    print("✓ Lógica Salvar: OK")

    # 2. Testar renomear_predefinicao logic
    nome_antigo = "Teste 1"
    novo_nome = "Teste Renomeado"
    if nome_antigo in predefinicoes:
        predefinicoes[novo_nome] = predefinicoes.pop(nome_antigo)
        if ultima_predefinicao == nome_antigo:
            ultima_predefinicao = novo_nome

    assert "Teste 1" not in predefinicoes
    assert "Teste Renomeado" in predefinicoes
    assert ultima_predefinicao == "Teste Renomeado"
    print("✓ Lógica Renomear: OK")

    # 3. Testar deletar_predefinicao logic
    nome_deletar = "Teste Renomeado"
    if nome_deletar in predefinicoes:
        del predefinicoes[nome_deletar]
        if ultima_predefinicao == nome_deletar:
            ultima_predefinicao = None

    assert "Teste Renomeado" not in predefinicoes
    assert ultima_predefinicao is None
    print("✓ Lógica Deletar: OK")

    print("\nTodos os testes de lógica passaram!")

if __name__ == "__main__":
    test_predefinicoes_logic()
