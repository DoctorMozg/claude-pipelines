# Mermaid Syntax by Diagram Type

Source: https://mermaid.js.org/intro/ (official Mermaid docs, versioned). Use this file via grep — locate the section for your diagram type, copy the skeleton, adapt the example. Do not load the whole file.

Each section has: syntax skeleton, key tokens, minimal working example.

## flowchart

Skeleton:

```
flowchart <direction>
    <nodeId>[<label>]
    <nodeId> --> <nodeId>
```

Direction tokens: `TD` (top-down), `LR` (left-right), `BT`, `RL`.

Node shapes:

- `id[Text]` — rectangle
- `id(Text)` — rounded rectangle
- `id([Text])` — stadium
- `id[[Text]]` — subroutine
- `id[(Text)]` — cylindrical (database)
- `id((Text))` — circle
- `id{Text}` — rhombus (decision)
- `id{{Text}}` — hexagon
- `id>Text]` — asymmetric

Edge types:

- `-->` solid arrow
- `---` solid line
- `-.->` dotted arrow
- `==>` thick arrow
- `-- text -->` labeled arrow
- `-.->|text|` dotted with label

Styling:

- `classDef name fill:#f9f,stroke:#333`
- `class nodeId name`
- `style nodeId fill:#bbf,stroke:#f66,stroke-width:2px`

Subgraphs:

```
subgraph title
    direction LR
    a --> b
end
```

Minimal example:

```
flowchart TD
    Start([User request]) --> Auth{Authenticated?}
    Auth -->|yes| Fetch[Fetch data]
    Auth -->|no| Login[Redirect to login]
    Fetch --> Render[Render page]
    Login --> Render
```

## sequenceDiagram

Skeleton:

```
sequenceDiagram
    participant A as <alias>
    participant B
    A->>B: <message>
    B-->>A: <response>
```

Key tokens:

- `participant X as <Label>` — declare actor (order controls column order)
- `actor X` — stick figure instead of box
- `->>` solid arrow with head (synchronous call)
- `-->>` dashed arrow with head (response)
- `-)` solid arrow open head (async)
- `--)` dashed arrow open head (async response)
- `-x` solid cross (lost message)
- `activate X` / `deactivate X` — lifeline activation bars
- `Note left of X: text` / `Note right of X:` / `Note over X,Y:`
- `loop <label> ... end`
- `alt <cond> ... else <cond> ... end`
- `opt <cond> ... end`
- `par <label> ... and <label> ... end`
- `rect rgb(200,220,240) ... end` — background highlight

Minimal example:

```
sequenceDiagram
    participant C as Client
    participant API
    participant DB
    C->>API: POST /orders
    activate API
    API->>DB: INSERT order
    DB-->>API: order_id
    API-->>C: 201 Created
    deactivate API
```

## classDiagram

Skeleton:

```
classDiagram
    class ClassName {
        +field: Type
        +method() ReturnType
    }
    ClassA <|-- ClassB
```

Visibility tokens: `+` public, `-` private, `#` protected, `~` package.

Annotations: `<<interface>>`, `<<abstract>>`, `<<enumeration>>`, `<<service>>`.

Relationships:

- `<|--` inheritance (extends)
- `*--` composition
- `o--` aggregation
- `-->` association (directed)
- `--` link
- `..>` dependency
- `..|>` realization (implements)
- `<--o` with cardinality: `"1" <-- "many"`

Generics: `List~User~`.

Minimal example:

```
classDiagram
    class Animal {
        <<abstract>>
        +name: string
        +makeSound() void
    }
    class Dog {
        +breed: string
        +makeSound() void
    }
    class Owner {
        +name: string
    }
    Animal <|-- Dog
    Owner "1" o-- "many" Dog : owns
```

## stateDiagram-v2

Skeleton:

```
stateDiagram-v2
    [*] --> StateA
    StateA --> StateB: event
    StateB --> [*]
```

Key tokens:

- `[*]` — start or end state (context-dependent)
- `-->` — transition
- `: label` — transition label (event/action)
- `state <id> { ... }` — composite state
- `--` inside composite state — concurrent regions
- `state "<label>" as <id>` — state with spaces
- `note left of X : text` / `note right of X`
- `state <id> <<choice>>` — choice pseudostate
- `state <id> <<fork>>` / `<<join>>` — fork/join

Minimal example:

```
stateDiagram-v2
    [*] --> Idle
    Idle --> Loading: fetch
    Loading --> Success: data received
    Loading --> Error: network failure
    Error --> Idle: retry
    Success --> [*]
```

## erDiagram

Skeleton:

```
erDiagram
    ENTITY_A ||--o{ ENTITY_B : relationshipLabel
    ENTITY_A {
        type fieldName PK "comment"
    }
```

Cardinality left/right:

- `|o` zero or one
- `||` exactly one
- `}o` zero or many
- `}|` one or many

Combine for both ends, e.g. `||--o{` = one to zero-or-many.

Identifier tokens: `PK` primary key, `FK` foreign key, `UK` unique key.

Minimal example:

```
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ ORDER_ITEM : contains
    PRODUCT ||--o{ ORDER_ITEM : appears_in
    CUSTOMER {
        int id PK
        string email UK
        string name
    }
    ORDER {
        int id PK
        int customer_id FK
        datetime placed_at
    }
```

## mindmap

Skeleton:

```
mindmap
  root((Root text))
    Branch1
      Leaf1
      Leaf2
    Branch2
```

Node shapes (same syntax family as flowchart):

- `id[Text]` square
- `id(Text)` rounded
- `id((Text))` circle
- `id))Text((` bang
- `id)Text(` cloud
- `id{{Text}}` hexagon
- Plain text — default

Indentation controls hierarchy (2 spaces per level). Use icons: `::icon(fa fa-book)`.

Minimal example:

```
mindmap
  root((Auth system))
    Identity
      Users
      Sessions
    Credentials
      Passwords
      OAuth
      API keys
    Policy
      Roles
      Permissions
```

## gitGraph

Skeleton:

```
gitGraph
    commit
    branch <name>
    checkout <name>
    commit
    merge main
```

Key tokens:

- `commit` — commit on current branch
- `commit id: "<id>"` — labeled commit
- `commit tag: "<tag>"` — tagged commit
- `commit type: HIGHLIGHT` — also `NORMAL`, `REVERSE`
- `branch <name>` — create and switch
- `checkout <name>` / `switch <name>` — switch branches
- `merge <name>` — merge branch into current
- `cherry-pick id: "<id>"`

Minimal example:

```
gitGraph
    commit id: "init"
    branch feature/auth
    checkout feature/auth
    commit id: "add login"
    commit id: "add tests"
    checkout main
    merge feature/auth tag: "v1.0"
    commit id: "hotfix"
```

## timeline

Skeleton:

```
timeline
    title <title>
    <period> : <event>
        : <event>
    <period> : <event>
```

Key tokens:

- `title` — top-level title
- `<period>` — any string (year, quarter, phase name)
- `: <event>` — event under current period; additional `: <event>` lines stack under the same period
- `section <name>` — group periods into colored sections

Minimal example:

```
timeline
    title Product rollout
    section Planning
        2025 Q1 : Market research
                : User interviews
        2025 Q2 : Spec written
                : Approval gate
    section Execution
        2025 Q3 : MVP launch
        2025 Q4 : GA release
```

## C4

Skeleton (context, container, component share the same family):

```
C4Context
    title <title>
    Person(alias, "Label", "Description")
    System(alias, "Label", "Description")
    Rel(fromAlias, toAlias, "Label", "Technology")
```

Family tokens:

- `C4Context` — system-in-environment view (Persons, Systems, System_Ext)
- `C4Container` — inside-one-system view (Container, ContainerDb, ContainerQueue)
- `C4Component` — inside-one-container view (Component, ComponentDb, ComponentQueue)
- `C4Dynamic` — runtime interaction view
- `C4Deployment` — deployment topology

Element tokens:

- `Person(alias, label, descr)` / `Person_Ext`
- `System(alias, label, descr)` / `System_Ext` / `SystemDb` / `SystemQueue`
- `Container(alias, label, technology, descr)` / `ContainerDb` / `ContainerQueue`
- `Component(alias, label, technology, descr)`
- `Boundary(alias, label, type) { ... }` — `Enterprise_Boundary`, `System_Boundary`, `Container_Boundary`
- `Rel(from, to, label, technology)` / `BiRel`
- `Rel_U`, `Rel_D`, `Rel_L`, `Rel_R` — directional hints

Minimal example:

```
C4Context
    title Payment system — context
    Person(customer, "Customer", "Places orders and pays")
    System(shop, "Shop", "Handles orders and payments")
    System_Ext(stripe, "Stripe", "Payment processor")
    System_Ext(email, "Email service", "Transactional email")
    Rel(customer, shop, "Places order / pays", "HTTPS")
    Rel(shop, stripe, "Charges card", "REST")
    Rel(shop, email, "Sends receipt", "SMTP")
```
