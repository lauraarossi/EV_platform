import enum
import datetime
from sqlalchemy import String, Float, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class FuelType(str, enum.Enum):
    """What a car buys, which is not quite the same as what it is.

    `hybrid` is the self-charging kind: it has a battery and a motor, it never
    plugs in, and every kilometre it travels was ultimately paid for at a pump.
    So it buys petrol, and its hybrid-ness shows up as a better L/100km rather
    than as a second fuel. A mild hybrid is the same story with a smaller
    battery, and a diesel one buys diesel — which is why those are recorded as
    plain diesel rather than as a hybrid that would be priced at petrol rates.

    `plugin_hybrid` is genuinely two cars. It draws from the grid and from a
    pump, in a proportion that depends on how often someone bothers to plug it
    in — which is why it needs a figure for each and a share between them, and
    why lumping it in with the self-charging sort got its running cost wrong in
    whichever direction that person actually drives.
    """

    electric = "electric"
    petrol = "petrol"
    diesel = "diesel"
    hybrid = "hybrid"
    plugin_hybrid = "plugin_hybrid"


class Transmission(str, enum.Enum):
    """Common transmissions, offered as suggestions rather than enforced.

    The column is free text: no catalogue we ingest records a transmission at
    all, so anything stored here is typed by a person, and real gearboxes are
    messier than a fixed list ("7-speed DSG", "e-CVT", "single-speed reduction
    gear"). These values just populate the dropdown.
    """

    single_speed = "single_speed"
    manual = "manual"
    automatic = "automatic"
    cvt = "cvt"
    dual_clutch = "dual_clutch"


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    make: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    trim: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer)
    fuel_type: Mapped[FuelType] = mapped_column(Enum(FuelType), default=FuelType.electric)
    # Free text, not an enum: see Transmission's docstring.
    transmission: Mapped[str | None] = mapped_column(String(60))

    # Electric side. Battery capacity turns a state-of-charge swing into kWh.
    battery_capacity_kwh: Mapped[float | None] = mapped_column(Float)
    onboard_charger_kw: Mapped[float | None] = mapped_column(Float)
    wltp_range_km: Mapped[float | None] = mapped_column(Float)
    # Quoted consumption, used to price this car as a hypothetical alternative.
    consumption_kwh_per_100km: Mapped[float | None] = mapped_column(Float)

    # How much of a plug-in hybrid's driving is done on the battery. Null for
    # everything else, where the question does not arise.
    #
    # There is no honest default: a plug-in charged nightly and driven to the
    # shops is nearly an EV, and the same car never plugged in is a heavy
    # petrol one. The official figures assume the former, which is why they
    # flatter it so badly, so this is asked rather than assumed.
    electric_share_pct: Mapped[float | None] = mapped_column(Float)

    # Liquid-fuel side, mirroring the two above: tank capacity turns a tank
    # percentage into litres, and the quoted figure prices the car hypothetically.
    engine_size_cc: Mapped[int | None] = mapped_column(Integer)
    tank_capacity_litres: Mapped[float | None] = mapped_column(Float)
    fuel_consumption_l_per_100km: Mapped[float | None] = mapped_column(Float)

    # Performance (shared)
    horsepower: Mapped[int | None] = mapped_column(Integer)
    zero_to_100_seconds: Mapped[float | None] = mapped_column(Float)
    top_speed_kmh: Mapped[int | None] = mapped_column(Integer)
    kerb_weight_kg: Mapped[int | None] = mapped_column(Integer)

    # Whether this is a car you actually have. Owned cars sit in the Garage and
    # can be logged against; the rest are in the Showroom, cars being weighed
    # up rather than driven.
    #
    # It changes nothing else: both hold the same specs, and either can be on
    # either side of a comparison. The split is about what you own, not about
    # what the car is for.
    is_owned: Mapped[bool] = mapped_column(default=True)

    nickname: Mapped[str | None] = mapped_column(String(100))
    # Remote URL rather than an upload: PaaS filesystems are ephemeral, so
    # storing bytes locally would lose the image on every redeploy.
    image_url: Mapped[str | None] = mapped_column(String(500))

    user: Mapped["User"] = relationship(back_populates="vehicles")
    fuel_events: Mapped[list["FuelEvent"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )
