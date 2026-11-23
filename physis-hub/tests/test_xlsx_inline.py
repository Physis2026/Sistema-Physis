"""xlsx gerado por programa (texto dentro da célula, sem sharedStrings) agora é lido (teste de arquivos de 23/11/2026)."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from physis_hub import mv_bots


class XlsxInline(unittest.TestCase):
    def test_inline_e_numeros(self):
        p = Path(tempfile.mkdtemp()) / "Physis_Integrado_v9.xlsx"
        folha = ('<worksheet><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Receita Casa</t></is></c>'
                 '<c r="B1"><v>1234.5</v></c></row></sheetData></worksheet>')
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("xl/workbook.xml", "<workbook/>")
            z.writestr("xl/worksheets/sheet1.xml", folha)
        t = mv_bots.texto_de(p)
        self.assertIn("Receita Casa", t)
        self.assertIn("1234.5", t)
