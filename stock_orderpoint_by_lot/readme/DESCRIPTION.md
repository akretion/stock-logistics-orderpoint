Replenish specific lots

Use case: paint pot

Paint pots can be in lots of colours.
You may to implement it in the following way:
- a product `paint pot`, tracked by lots
- each lot is for one color
- lot name is a RAL name (a colour management system)
- lots are created when needed
- paint pot are managed by orderpoints (Make To Stock)

Without this module, if you have 10 pots RAL 2017 in stock
and there is a MO consumming 4 pots RAL 4012.
An orderpoint will not be triggered.

With this module, an orderpoint will allow to replenish the 
4 pots RAL 4012.
