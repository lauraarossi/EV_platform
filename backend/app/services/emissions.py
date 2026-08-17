"""CO2 from the driving actually logged.

A third axis beside cost and consumption, and the one where the two fuels are
least alike: a litre of petrol emits the same wherever it is burned, while an
EV's emissions happen at the power station and depend entirely on what the grid
was running on.

**Scope.** This counts CO2 from burning the fuel and from generating the
electricity. It excludes everything upstream — extracting and refining the
fuel, building the car, making the battery. That makes the two sides
comparable on the same terms, but it is not a full lifecycle figure, and the
interface says so rather than implying otherwise.
"""

from __future__ import annotations

from app.config import settings
from app.models.vehicle import FuelType

# Burning a litre releases the carbon in it. These follow from the fuel's
# composition rather than being measurements of any particular engine, which is
# why an efficient car and a thirsty one emit the same per litre — the
# difference shows up in how many litres it takes.
#
# The same constants the EEA uses to convert its CO2 figures back into
# consumption, so the catalogue and these numbers agree.
CO2_G_PER_LITRE = {
    FuelType.petrol: 2392.0,
    FuelType.diesel: 2640.0,
    # A hybrid still burns petrol; the electric half is counted separately.
    FuelType.hybrid: 2392.0,
}


def grid_intensity() -> float:
    """Grams of CO2 per kWh delivered by the grid.

    Configurable because it is the one figure here that is neither physical nor
    stable: it varies by country, and in Ireland it falls year on year as more
    wind comes online. Set GRID_CO2_G_PER_KWH to a current published figure for
    your grid rather than trusting the default.
    """
    return settings.grid_co2_g_per_kwh


def from_litres(litres: float | None, fuel: FuelType | None) -> float:
    """Grams of CO2 from burning `litres` of this car's fuel."""
    if not litres:
        return 0.0
    return litres * CO2_G_PER_LITRE.get(fuel or FuelType.petrol, CO2_G_PER_LITRE[FuelType.petrol])


def from_kwh(kwh: float | None) -> float:
    """Grams of CO2 from generating `kwh` of electricity."""
    if not kwh:
        return 0.0
    return kwh * grid_intensity()


def total(kwh: float | None, litres: float | None, fuel: FuelType | None) -> float:
    """Grams of CO2 from both sides, which a plug-in hybrid has at once."""
    return from_kwh(kwh) + from_litres(litres, fuel)
