# APIs Públicas  
## Manual para el Desarrollador  

### Central de Deudores v1.0

---

## Tabla de contenido

- Tabla de contenido
- Documentación de la API de Central de Información
- Introducción
- Control de Tráfico
- Autenticación
- Endpoints  
  - Deudas  
  - Históricas  
  - Cheques Rechazados
- Historial de versiones

---

## Documentación de la API de Central de Información

### Introducción

El servicio API de Central de deudores permite obtener un informe consolidado por clave de identificación fiscal (CUIT, CUIL o CDI) para una persona humana o jurídica respecto de financiaciones otorgadas por entidades financieras, fideicomisos financieros, entidades no financieras emisoras de tarjetas de crédito y/o compra, otros proveedores no financieros de créditos, sociedades de garantía recíproca, fondos de garantía de carácter público y proveedores de servicios de crédito entre particulares a través de plataformas. Además, cheques rechazados.

Su difusión no implica conformidad por parte de este Banco Central.

---

### Control de Tráfico

A fin de no saturar las comunicaciones, se establecen distintas reglas de control del tráfico proveniente de los clientes basado en las direcciones IP.

---

### Autenticación

No requerida.

---

## Endpoints

A continuación, se presentan los endpoints disponibles en la API. Cada endpoint incluye información sobre su propósito, el método HTTP que utiliza, los parámetros necesarios y un ejemplo de la respuesta que se puede esperar.

---

## Deudas

Este método permite obtener la situación crediticia, el monto de deuda, los días de atraso y observaciones correspondientes al último período informado por las entidades al BCRA para un CUIT/CUIL/CDI.

Los derechos de rectificación, actualización, supresión y confidencialidad deben ejercerse ante la entidad cedente que sea parte en la relación jurídica a que se refiere el dato impugnado.

A solicitud de cada cliente, dentro de los 10 días corridos del pedido, la entidad deberá comunicarle la última clasificación que le ha asignado, junto con los fundamentos que la justifican según la evaluación realizada por la entidad, el importe total de deudas con el sistema financiero y las clasificaciones asignadas que surjan de la última información disponible en la “Central de Deudores del Sistema Financiero”. Los clientes deberán ser notificados de que tienen la posibilidad de requerir esos datos, en el momento de presentarse las solicitudes de crédito, mediante una fórmula independiente de ellas.

---

### Parameters Request

| Nombre          | Tipo | Tipo Parámetro | Descripción                                                                 | Default |
|-----------------|------|----------------|-----------------------------------------------------------------------------|---------|
| identificacion  | Int  | Path           | Corresponde a CUIT/CUIL/CDI, la misma debe tener una longitud de 11 caracteres. |         |

---

### HTTP Request

```http
GET api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/identificacion
```

---

### Ejemplo Response OK

```json
{
  "status": 200,
  "results": {
    "identificacion": "***********",
    "denominacion": "***********",
    "periodos": [
      {
        "periodo": "202407",
        "entidades": [
          {
            "entidad": "BANCO DE LA NACION ARGENTINA",
            "situacion": 1,
            "fechaSit": "2024-05-30",
            "monto": 59.0,
            "diasAtrasoPago": 0,
            "refinanciaciones": false,
            "recategorizacionOblig": false,
            "situacionJuridica": false,
            "irrecDisposicionTecnica": false,
            "enRevision": false,
            "procesoJud": false
          }
        ]
      }
    ]
  }
}
```

A continuación, se detallan los campos retornados por el servicio:

### Campos retornados por el servicio (Deudas)

| Propiedades | Descripción |
|---|---|
| **Identificación** | CUIT/CUIL/CDI ingresado |
| **Denominación** | Nombre o razón social de la persona humana o jurídica que figura en el padrón de la Administración Federal de Ingresos Públicos (AFIP) o bien la que fuera registrada por la entidad informante. |
| **Período** | En formato AAAAMM, indica el último período informado por la entidad. |
| **Entidad** | Denominación de la entidad informante. |
| **Situación** | Indica la clasificación del deudor informada por la entidad. Para más información, acceder al Texto ordenado de las normas sobre Clasificación de deudores.  \n\n- **Situación 1:**  \n  - En situación normal \| Cartera comercial, ver sección 6, punto 6.5.1.  \n  - Situación normal \| Cartera para consumo o vivienda, ver sección 7, punto 7.2.1.  \n\n- **Situación 2:**  \n  - Con seguimiento especial \| Con seguimiento especial \| Cartera comercial, ver sección 6, punto 6.5.2.  \n  - Riesgo bajo \| Cartera para consumo o vivienda, ver sección 7, punto 7.2.2.  \n\n- **Situación 3:**  \n  - Con problemas \| Cartera comercial, ver sección 6, punto 6.5.3.  \n  - Riesgo medio \| Cartera para consumo o vivienda, ver sección 7, punto 7.2.3.  \n\n- **Situación 4:**  \n  - Con alto riesgo de insolvencia \| Cartera comercial, ver sección 6, punto 6.5.4.  \n  - Riesgo alto \| Cartera para consumo o vivienda, ver sección 7, punto 7.2.4.  \n\n- **Situación 5:**  \n  - Irrecuperable \| Cartera comercial, ver sección 6, punto 6.5.5.  \n  - Irrecuperable \| Cartera para consumo o vivienda, ver sección 7, punto 7.2.5. |
| **FechaSit1** | Fecha desde que se encuentra en situación 1. |
| **Monto** | Información en miles de pesos. |
| **DiasAtraso** | Según lo determinado en el punto 8. del apartado B del TO **"Régimen Informativo Contable Mensual - Deudores del Sistema Financiero"**. Si el deudor perteneciente a la cartera para consumo o vivienda en situación distinta a la normal se encuentra clasificado por refinanciaciones, recategorización obligatoria, situación jurídica (concordatos judiciales o extrajudiciales, concurso preventivo, gestión judicial o quiebra) o irrecuperable por disposición técnica, se informarán los días de atraso. El valor **(0)** indica **"No Aplicable"**. |
| **Refinanciaciones** | Encuadre de situación “Refinanciaciones”, que se ha establecido en el punto 8.1. del apartado B. del TO Régimen Informativo Contable Mensual - Deudores del Sistema Financiero. |
| **RecategorizacionOblig** | Encuadre de situación “Recategorización obligatoria”, que se ha establecido en el punto 8.1. del apartado B. del TO Régimen Informativo Contable Mensual - Deudores del Sistema Financiero. |
| **SituacionJuridica** | Encuadre de situación “Situación jurídica (concordatos judiciales o extrajudiciales, concurso preventivo, gestión judicial o quiebra)”, que se ha establecido en el punto 8.1. del apartado B. del TO Régimen Informativo Contable Mensual - Deudores del Sistema Financiero. |
| **IrrecDisposicionTecnica** | Encuadre de situación “Irrecuperable por Disposición Técnica”, que se ha establecido en el punto 8.1. del apartado B. del TO Régimen Informativo Contable Mensual - Deudores del Sistema Financiero. |
| **EnRevision** | Información sometida a revisión (Ley 25.326, art. 16, inc 6) |
| **Procesojud** | Información sometida a proceso judicial (Ley 25.326, art. 38, inc. 3) |

---

### Ejemplo Response Server Error

```json
{
  "status": 500,
  "errorMessages": [
    "Se produjo un error al ejecutar la acción."
  ]
}
```

---

### Ejemplos Response Bad Resquest

```http
GET api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/123456789
```

```json
{
  "status": 400,
  "errorMessages": [
    "Parámetro erróneo: Ingresar 11 dígitos para realizar la consulta."
  ]
}
```

---

### Ejemplo Response Not Found

```http
GET api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/12345678912
```

```json
{
  "status": 404,
  "errorMessages": [
    "No se encontró datos para la identificación ingresada."
  ]
}
```

---

## Históricas

Este método permite obtener para un CUIT/CUIL/CDI la situación crediticia relativa a los últimos 24 meses.

### Parameters Request

| Nombre | Tipo | Tipo Parámetro | Descripción | Default |
|---|---|---|---|---|
| identificacion | Int | Path | Corresponde a CUIT/CUIL/CDI, la misma debe tener una longitud de 11 caracteres. | |

### HTTP Request

```http
GET api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/Historicas/identificacion
```

### Ejemplo Response OK

```json
{
  "status": 200,
  "results": {
    "identificacion": "***********",
    "denominacion": "***********",
    "periodos": [
      {
        "periodo": "202403",
        "entidades": [
          {
            "entidad": "BANCO DE LA NACION ARGENTINA",
            "situacion": 1,
            "monto": 35.0,
            "enRevision": false,
            "procesoJud": false
          }
        ]
      },
      {
        "periodo": "202402",
        "entidades": [
          {
            "entidad": "BANCO DE LA NACION ARGENTINA",
            "situacion": 1,
            "monto": 41.0,
            "enRevision": false,
            "procesoJud": false
          }
        ]
      },
      ...
    ]
  }
}
```

A continuación, se detallan los campos retornados por el servicio:

| Propiedades | Descripción |
|---|---|
| **Identificación** | CUIT/CUIL/CDI ingresado |
| **Denominación** | Nombre o razón social de la persona humana o jurídica que figura en el padrón de la Administración Federal de Ingresos Públicos (AFIP) o bien la que fuera registrada por la entidad informante. |
| **Período** | En formato AAAAMM, indica el último período informado por la entidad. |
| **Entidad** | Denominación de la entidad informante. |
| **Situación** | Indica la clasificación del deudor informada por la entidad. Para más información, acceder al Texto ordenado de las normas sobre Clasificación de deudores.  \n\n- **Situación 1:**  \n  - En situación normal \| Cartera comercial, ver sección 6, punto 6.5.1.  \n  - Situación normal \| Cartera para consumo o vivienda, ver sección 7, punto 7.2.1.  \n\n- **Situación 2:**  \n  - Con seguimiento especial \| Con seguimiento especial \| Cartera comercial, ver sección 6, punto 6.5.2.  \n  - Riesgo bajo \| Cartera para consumo o vivienda ver sección 7, punto 7.2.2.  \n\n- **Situación 3:**  \n  - Con problemas \| Cartera comercial, ver sección 6, punto 6.5.3.  \n  - Riesgo medio \| Cartera para consumo o vivienda ver sección 7, punto 7.2.3.  \n\n- **Situación 4:**  \n  - Con alto riesgo de insolvencia \| Cartera comercial, ver sección 6, punto 6.5.4.  \n  - Riesgo alto \| Cartera para consumo o vivienda, ver sección 7, punto 7.2.4.  \n\n- **Situación 5:**  \n  - Irrecuperable \| Cartera comercial, ver sección 6, punto 6.5.5.  \n  - Irrecuperable \| Cartera para consumo o vivienda, ver sección 7, punto 7.2.5. |
| **Monto** | Información en miles de pesos. |
| **EnRevision** | Información sometida a revisión (Ley 25.326, art. 16, inc 6) |
| **Procesojud** | Información sometida a proceso judicial (Ley 25.326, art. 38, inc. 3) |

---

### Ejemplo Response Server Error

```json
{
  "status": 500,
  "errorMessages": [
    "Se produjo un error al ejecutar la acción."
  ]
}
```

---

### Ejemplos Response Bad Resquest

```http
GET api.bcra.gob.ar/CentralDeInformacion/v1.0/Deudas/Historicas/123456789
```

```json
{
  "status": 400,
  "errorMessages": [
    "Parámetro erróneo: Ingresar 11 dígitos para realizar la consulta."
  ]
}
```

---

### Ejemplo Response Not Found

```http
GET api.bcra.gob.ar/CentralDeInformacion/v1.0/Deudas/Historicas/12345678912
```

```json
{
  "status": 404,
  "errorMessages": [
    "No se encontró datos para la identificación ingresada."
  ]
}
```

## Cheques Rechazados

Este método permite obtener para un CUIT/CUIL/CDI los cheques rechazados con sus correspondientes causales.

Estas consultas se realizan sobre la Central de cheques rechazados, conformada por datos recibidos diariamente de los bancos, que se publican sin alteraciones de acuerdo con los plazos dispuestos en el inciso 4 del artículo 26 de la Ley 25.326 de Protección de los Datos Personales y con el criterio establecido en el punto 1.3. de la Sección 1 del Texto ordenado Centrales de Información. Su difusión no implica conformidad por parte de este Banco Central.

### Parameters Request

| Nombre | Tipo | Tipo Parámetro | Descripción | Default |
|---|---|---|---|---|
| identificacion | Int | Path | Corresponde a CUIT/CUIL/CDI, la misma debe tener una longitud de 11 caracteres. | |

### HTTP Request

```http
GET api.bcra.gob.ar/CentralDeDeudores/v1.0/Deudas/ChequesRechazados/identificacion
```

### Ejemplo Response OK

```json
{
  "status": 200,
  "results": {
    "identificacion": "***********",
    "denominacion": "***********",
    "causales": [
      {
        "causal": "SIN FONDOS",
        "entidades": [
          {
            "entidad": 1,
            "detalle": [
              {
                "nroCheque": 752395,
                "fechaRechazo": "2024-04-08",
                "monto": 115000.00,
                "fechaPago": null,
                "fechaPagoMulta": null,
                "estadoMulta": "IMPAGA",
                "ctaPersonal": false,
                "denomJuridica": "HM COLON MONTAJES INDUSTRIALES S. R. L.",
                "enRevision": false,
                "procesoJud": false
              }
              ...
            ]
          }
          ...
        ]
      }
      ...
    ]
  }
}
```

A continuación, se detallan los campos retornados por el servicio:

| Propiedades | Descripción |
|---|---|
| **Identificación** | CUIT/CUIL/CDI ingresado |
| **Denominación** | Nombre o razón social de la persona humana o jurídica que figura en el padrón de la Administración Federal de Ingresos Públicos (AFIP) o bien la que fuera registrada por la entidad informante. |
| **Causal** | Motivo del rechazo (Sin fondos – Defectos formales). |
| **Entidad** | Corresponde un número de agrupamiento por banco. |
| **NroCheque** | Número de cheque rechazado. |
| **FechaRechazo** | Fecha que se realizó el rechazo. |
| **Monto** | Monto del cheque rechazado. |
| **FechaPago** | Fecha que se realizó el levantamiento del cheque. |
| **FechaPagoMulta** | Fecha que se realizó el pago de la multa. (*EstadoMulta* = null) |
| **EstadoMulta** | Para los casos que no posea fecha de pago de multa (“fechaPagoMulta” = null), se informará el estado de esta (IMPAGA, SUSPENDIDO, SUSPENDIDA). |
| **CtaPersonal** | Si la consulta se realiza para un CUIT/CUIL/CDI correspondiente a una persona humana se indicará siempre “CtaPersonal” = true. En el caso que la consulta se efectúe para una persona jurídica se indicará siempre “CtaPersonal” = false. |
| **DenomJuridica** | En el caso que la consulta se realice para un CUIT/CUIL/CDI de persona humana y se trate de un cheque vinculado con una persona jurídica, se informará la denominación de la empresa. Si la consulta se realiza para una persona jurídica el campo siempre estará vacío (“null”). |
| **EnRevision** | Información sometida a revisión (Ley 25.326, art. 16, inc 6) |
| **Procesojud** | Información sometida a proceso judicial (Ley 25.326, art. 38, inc. 3) |

---

### Ejemplo Response Server Error

```json
{
  "status": 500,
  "errorMessages": [
    "Se produjo un error al ejecutar la acción."
  ]
}
```

---

### Ejemplo Response BAD REQUEST

```http
GET api.bcra.gob.ar/CentralDeInformacion/v1.0/Deudas/ChequesRechazados/123456789
```

```json
{
  "status": 400,
  "errorMessages": [
    "Parámetro erróneo: Ingresar 11 dígitos para realizar la consulta."
  ]
}
```

---

## Historial de versiones

| Versión | Fecha de Lanzamiento | Fecha de Desactivación | Observación |
|---|---|---|---|
| v1.0 | 29/08/2024 |  |  |




