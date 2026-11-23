"""Comprobaciones ligeras de los resultados históricos del artículo.

No se recalculan las 1.080 simulaciones; estas pruebas verifican que los
archivos publicados sean internamente consistentes y rastreables.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "resultados"


def leer_csv(nombre):
    with (OUT / nombre).open(newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


class IntegridadResultados(unittest.TestCase):
    def test_diseno_factorial_y_trazas_compartidas(self):
        filas = leer_csv("replicas.csv")
        self.assertEqual(len(filas), 1080)
        grupos = Counter((f["load"], f["vms"], f["policy"], f["failure"]) for f in filas)
        self.assertEqual(len(grupos), 36)
        self.assertEqual(set(grupos.values()), {30})
        hashes = defaultdict(set)
        for f in filas:
            hashes[(f["load"], f["seed"])].add(f["trace_sha256"])
        self.assertEqual(len(hashes), 90)
        self.assertTrue(all(len(digests) == 1 for digests in hashes.values()))

    def test_conservacion_y_proporciones(self):
        for f in leer_csv("replicas.csv"):
            ofrecidas = int(f["offered"])
            total = sum(int(f[k]) for k in ("correct", "rejected", "expired", "failed"))
            self.assertEqual(ofrecidas, total)
            self.assertLessEqual(int(f["good"]), int(f["correct"]))
            self.assertAlmostEqual(float(f["availability"]), int(f["correct"]) / ofrecidas)
            self.assertAlmostEqual(float(f["timely"]), int(f["good"]) / ofrecidas)

    def test_seleccion_y_costos(self):
        data = json.loads((OUT / "decision.json").read_text(encoding="utf-8"))
        candidatos = data["candidates"]
        self.assertEqual(len(candidatos), 6)
        self.assertEqual({(c["vms"], c["policy"]) for c in candidatos},
                         {(n, b) for n in (4, 6, 8) for b in ("RR", "MP")})
        factibles = [c for c in candidatos if c["feasible"]]
        self.assertEqual(len(factibles), 2)
        self.assertTrue(all(c["vms"] == 8 for c in factibles))
        esperado = min(factibles, key=lambda c: (c["cost"], c["max_p95"]))
        self.assertEqual(data["selected"], esperado)
        self.assertEqual((esperado["vms"], esperado["policy"]), (8, "MP"))
        self.assertGreaterEqual(esperado["min_availability"], .99)
        self.assertGreaterEqual(esperado["min_timely"], .95)

    def test_huellas_de_fuentes_originales(self):
        data = json.loads((OUT / "metadatos.json").read_text(encoding="utf-8"))
        self.assertEqual(data["replicas"], 30)
        self.assertEqual(data["executions"], 1080)
        for nombre, esperado in data["source_sha256"].items():
            calculado = hashlib.sha256((ROOT / nombre).read_bytes()).hexdigest()
            self.assertEqual(calculado, esperado, f"Archivo modificado: {nombre}")


if __name__ == "__main__":
    unittest.main()
