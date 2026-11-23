"""Arquivos de registro de correções ficam fora das regras do bot documentos (decisão de 23/11/2026)."""
import unittest

from physis_hub import mv_bots


class Registros(unittest.TestCase):
    def test_fora_das_regras(self):
        for n in ("Doc 1_ Resumo Executivo (2027–2031) [PT]_v2_TESTE_mudancas.md", "33_Revisao_Apresentacoes.md",
                  "34_Revisao_Documentos_Estrategicos_e_Rascunhos.md", "48_Fonte_da_Verdade_e_Atualizacao_Documentos_TESTE.md",
                  "48a_Mapa_Roadmap_e_Strategic_Architecture_TESTE.md", "48b_Mapa_Estrategias_TESTE.md",
                  "49_Checklist_Documentos_em_Desenvolvimento_para_Aprovacao.md", "CHECKLIST.md", "MV.md", "ROADMAP.md",
                  "27_Decisoes.md"):
            self.assertTrue(mv_bots.SEM_REGRAS.match(n), n)

    def test_documentos_continuam_conferidos(self):
        for n in ("01_Memorial_Tecnico.docx", "15_Plano_de_Negocios.docx", "41_Mapa_Proposito_5_Frentes.md",
                  "37_Missao_Visao_por_Entidade_RASCUNHO.md", "32_Levantar_e_Resolver_Antes_de_Implementar.md", "Roadmap_Casa.docx"):
            self.assertFalse(mv_bots.SEM_REGRAS.match(n), n)
