# Keywords

There are a few keywords:

- unsafe
- public/private/internal
- @ 

## The "@" keyword
 
Everything prefixed by an "@" serves as a "compiler call". These are things where the compiler
needs to actively do something and which aren't just a replacement/const.

Examples:

- ``@"something.something"()`` calls the function `something.something`, **NOT** the function `something`
in the module/class ``something``.
- ``@import("module_name")`` imports the module into the current module's dependencies.


# Modules

- Specified to import via ``@import("module.module.module")``