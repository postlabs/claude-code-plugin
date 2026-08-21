"""The neutral **spark** interactive-controller DSL kernel — a strict LEAF.

A *spark* is the interactive half of a *spread*: where a spread is a READ-ONLY
render definition, a spark binds a view anchor to an EFFECT (this slice: ``act``
— bake a target dough with a datum-mapped input). It mirrors ``app/spreads/``
one-for-one (model + catalog + ``$``-anchor resolver + validator) and imports
NOTHING from ``app.doughs`` / ``app.memo``; both import DOWNWARD into it. The one
sanctioned sideways edge is ``app.spreads.spark`` → ``app.spreads`` (both neutral
leaves; ``app.spreads`` imports nothing back).

Every consumer imports the submodule directly (``from app.spreads.spark.model import
Spark``); this package root has no re-export barrel.
"""
