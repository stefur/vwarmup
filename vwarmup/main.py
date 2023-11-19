import argparse
import asyncio
from weconnect import weconnect, addressable
from weconnect.elements.climatization_status import ClimatizationStatus
from pyeasee import Easee


async def weconnect_listener(args) -> None:
    """Connect to WeConnect and listen to events"""
    print("# Initialize WeConnect")
    connection = weconnect.WeConnect(
        username=args.vwusername,
        password=args.vwpassword,
        updateAfterLogin=False,
        loginOnInit=False,
    )
    print("# Login to WeConnect")
    connection.login()
    print("# Register for events")
    event_handler = create_event_handler(args)
    connection.addObserver(
        event_handler,
        addressable.AddressableLeaf.ObserverEvent.VALUE_CHANGED,
    )
    while True:
        print("# Update")
        connection.update()
        await asyncio.sleep(300)


def create_event_handler(args):
    """Create the event handler"""

    def event_handler(
        element: addressable.AddressableAttribute,
        flags: addressable.AddressableLeaf.ObserverEvent,
    ) -> None:
        """Handle events"""
        if (
            flags & addressable.AddressableLeaf.ObserverEvent.VALUE_CHANGED
            and element.getLocalAddress() == "climatisationState"
        ):
            match element.value:
                case ClimatizationStatus.ClimatizationState.OFF:
                    print("# Climatization is off.")
                    asyncio.create_task(toggle_smart_charging(args))
                case ClimatizationStatus.ClimatizationState.INVALID:
                    print("# Invalid climatization state.")
                case ClimatizationStatus.ClimatizationState.UNKNOWN:
                    print("# Unknown climatization state.")
                case _:
                    print("# Climatization is on.")
                    asyncio.create_task(toggle_smart_charging(args))

    return event_handler


async def toggle_smart_charging(args) -> None:
    """Toggle smart charging mode"""
    print("# Logging in to Easee.")
    easee = Easee(args.easeeusername, args.easeepassword)
    print("# Success!")
    sites = await easee.get_sites()
    home = sites[0]
    circuits = home.get_circuits()
    the_circuit = circuits[0]
    chargers = the_circuit.get_chargers()
    the_charger = chargers[0]
    state = await the_charger.get_state()
    if state["smartCharging"] and state["chargerOpMode"] == "AWAITING_START":
        print("# Turning off smart charging.")
        await the_charger.smart_charging(False)

    elif state["smartCharging"] is False:
        print("# Turning on smart charging.")
        await the_charger.smart_charging(True)
    else:
        print("# Nothing to do.")
    await easee.close()


async def main():
    parser = argparse.ArgumentParser(
        prog="vwarmup",
        description="Listen to WeConnect events and control the Easee charging box",
    )
    parser.add_argument(
        "-vwu", "--vwusername", help="Username of Volkswagen id", required=True
    )
    parser.add_argument(
        "-vwp", "--vwpassword", help="Password of Volkswagen id", required=True
    )
    parser.add_argument(
        "-eu", "--easeeusername", help="Username of Easee account", required=True
    )
    parser.add_argument(
        "-ep", "--easeepassword", help="Password of Easee account", required=True
    )
    args = parser.parse_args()

    await asyncio.gather(asyncio.create_task(weconnect_listener(args)))


# Run the main function
asyncio.run(main())
