# Accessory Checks (Closures, Rivets, Trim, Gutter, Downspout)

## Closures
Detected types:
- Metal Inside Closure (e.g. CL426)
- Metal Outside Closure
- Foam Inside / Outside Closure
- Universal Closure

**Rule:** If panels are present and zero closures are found → WARNING.

## Pop Rivets
Patterns: pop rivet, blind rivet, FU13, FU15, 1/8" & 3/16" rivets.

**Rule:** Trim present but no rivets → WARNING.

## Trim
Detects eave, rake, corner, base, jamb, header, ridge, valley, transition, flashing, etc.
Reports piece count, unique marks, and approximate total length when available.

## Gutter & Downspout
**Rule:** Roof panels present but no gutter → WARNING  
**Rule:** Roof panels present but no downspout → WARNING

These checks are intentionally conservative (presence / basic quantity).  
Detailed length-vs-building-perimeter calculations can be added once drawings reliably expose eave lengths.
