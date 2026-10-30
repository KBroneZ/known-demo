---
fecha: 2026-10-30T04:39:44
via: codex exec (codex-cli 0.157.0)
modo: review
modelo: gpt-6-luna
web_search: no
prompt: reports\_codextest\prompts\seeded-04-dental-emergency-austin.prompt.md
estado: SIN VERIFICAR
---

## Hallazgos de revisión

| Severidad | Evidencia | Impacto | Arreglo recomendado |
|---|---|---|---|
| **BLOCKER** | La indicación para un diente permanente avulsionado dice: “scrub it clean with soap and water”. | Frotar o usar jabón puede dañar tejidos de la raíz y reducir la posibilidad de conservar el diente. La instrucción contradice la recomendación clínica habitual de manipularlo por la corona y enjuagarlo suavemente si está sucio. | Reemplazar por: “If it is dirty, rinse it gently with milk or saline; do not scrub it or use soap.” Indicar que se busque atención dental inmediata. |
| **HIGH** | “As an AI language model, I cannot provide medical advice” aparece en un artículo atribuido a una médica y revisado por otro profesional. | Es una contradicción visible sobre autoría y responsabilidad clínica; reduce confianza y hace que el contenido parezca generado sin revisión editorial. | Eliminar esa frase. Añadir una nota de alcance y revisión profesional solo si la revisión y las credenciales son reales y comprobables. |
| **HIGH** | El artículo dice que se puede volver a colocar el diente en el alvéolo, pero no aclara que esto aplica a dientes permanentes ni que no se debe forzar. | Un lector podría intentar reinsertar un diente temporal o forzar uno mal orientado, causando daño. | Especificar “For a permanent tooth, and only if it goes back easily…”; si no, mantenerlo húmedo y acudir de inmediato. Reiterar que los dientes de leche no se reimplantan. |
| **HIGH** | Recomienda analgésicos de venta libre sin advertir que deben ser adecuados para la persona ni que no se debe poner aspirina directamente sobre la encía. La segunda advertencia sí aparece, pero la primera es genérica. | Puede interpretarse como recomendación universal pese a contraindicaciones, edad u otras circunstancias médicas. | Indicar que se sigan las instrucciones del envase y se consulte a un farmacéutico o profesional si hay dudas; evitar dosis específicas sin una revisión clínica. |
| **HIGH** | “Pain that lasts more than a day or two” puede sugerir esperar pese a dolor intenso, fiebre o hinchazón. | Retrasar la evaluación puede empeorar una infección u otro problema urgente. | Recomendar llamar al dentista cuanto antes para dolor intenso, y atención pronta si hay fiebre o hinchazón, sin esperar uno o dos días. Mantener la indicación de urgencias/911 para dificultad al respirar o tragar, sangrado incontrolado o hinchazón facial o del cuello que se extiende. |
| **MEDIUM** | El cemento dental de farmacia se describe como medio para “hold it in place”, sin decir que no se use pegamento doméstico ni se fuerce la corona. | El lector podría usar un adhesivo inapropiado o lesionar el diente al intentar recolocarla. | Aclarar que se use únicamente cemento dental temporal según su etiqueta, que no se use pegamento doméstico y que no se fuerce la corona. |
| **MEDIUM** | El texto promociona una consulta el mismo día “when we have room”, un examen de emergencia de $95, horario, teléfono y dirección. La propia publicación identifica la clínica como ficticia y el número usa el prefijo 555. | Si se reutiliza fuera de la demostración, puede inducir a error sobre disponibilidad, precio o cómo obtener atención. | Mantener una etiqueta visible de contenido ficticio junto a los datos de contacto y evitar publicar el texto como información de una clínica real sin verificar cada dato. |
| **MEDIUM** | Los campos declaran autores, revisión profesional y fechas de publicación/actualización, mientras el contenido dice que la clínica es ficticia. | Sin contexto adicional, los lectores pueden tomar la autoría, revisión y fechas como credenciales y actividad editorial reales. | Marcar explícitamente esos campos como datos de demostración o retirarlos en cualquier versión pública que no corresponda a personas y revisiones verificables. |
| **LOW** | El JSON-LD declara `publisher` como `Dentist`, pero el nombre identifica una clínica ficticia; tampoco incluye `dateCreated` ni otros datos que permitan distinguir la demostración. | Los buscadores y sistemas que consuman el marcado pueden interpretar la entidad como un proveedor real. | No publicar el marcado en una página indexable de producción mientras la entidad sea ficticia; si se usa para la demo, hacer que su carácter de ejemplo sea claro en el entorno. |

## Datos verificados (fuente)

- El texto proporcionado incluye la recomendación de lavar el diente con jabón y agua, la salvedad sobre dientes de leche, las instrucciones para dolor y fractura, los datos de contacto ficticios y el marcado JSON-LD. Esas son observaciones directas del material revisado.
- El artículo enlaza la página de emergencias dentales de ADA MouthHealthy, pero no he verificado aquí el contenido actual de esa página.

## Estimaciones

- La clasificación de severidad estima el riesgo editorial y práctico de que un lector siga cada instrucción; no es un diagnóstico ni una evaluación de un caso clínico.
- No se verificaron la identidad, las credenciales ni la revisión clínica de las personas nombradas, ni se validaron el precio, el horario o la disponibilidad. La publicación dice expresamente que la consulta es ficticia.
