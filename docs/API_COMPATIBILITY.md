# Política de compatibilidad de la API

Esta política acompaña el contrato HTTP actual y permite evolucionar el
backend sin romper el dashboard HTML ni futuros clientes Vue.

## Contrato estable

Mientras `GET /api/system/capabilities` informe `api_version: "1"`, se
consideran compatibles:

- agregar campos opcionales a una respuesta JSON;
- agregar endpoints nuevos;
- agregar valores opcionales a una petición cuando los clientes existentes no
  deban enviarlos;
- agregar features nuevas con valor booleano en `capabilities`;
- corregir implementación interna sin alterar semántica observable.

Requieren migración explícita o una nueva versión:

- eliminar o renombrar una URL, método o campo existente;
- cambiar tipo, unidad o significado de un campo;
- convertir un campo opcional en obligatorio;
- cambiar códigos HTTP que un cliente pueda usar para decidir flujo;
- cambiar formato JPEG, MJPEG, ZIP o nombres de parámetros;
- normalizar unilateralmente los envelopes históricos de error.

El orden de campos JSON no forma parte del contrato. Los clientes deben
ignorar campos desconocidos y consultar `features` antes de usar un módulo.

## Estrategia de evolución

1. Mantener `/api/...` y `api_version: "1"` durante la estabilización actual.
2. Aplicar adiciones compatibles sobre v1 y reflejarlas en OpenAPI y tests.
3. Ante un cambio incompatible, preferir convivencia temporal de endpoints o
   un prefijo nuevo (`/api/v2`) antes que reinterpretar silenciosamente v1.
4. Marcar deprecaciones en documentación y, cuando exista un frontend externo,
   conservar una ventana de migración definida.
5. Retirar contratos sólo después de comprobar todos sus consumidores.

## Fuentes del contrato

- `docs/API.md`: inventario y semántica humana.
- `docs/openapi.json`: operaciones y modelos reutilizables para tooling.
- `tests/test_api_contracts.py`: correspondencia ejecutable con Flask.

El código vigente sigue siendo la fuente de verdad ante contradicciones. Una
contradicción entre estas tres representaciones es un defecto que debe
resolverse antes de publicar un frontend nuevo.
