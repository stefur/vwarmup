import argparse
import asyncio
import logging
from weconnect import weconnect, addressable
from weconnect.elements.timer import LOG
from weconnect.elements.climatization_status import ClimatizationStatus
from pyeasee import Easee

logger = logging.getLogger(__name__)

# Create a handler that prints log messages to stdout
stream_handler = logging.StreamHandler()

# Create a formatter and set it on the handler
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
stream_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(stream_handler)


async def weconnect_listener(args) -> None:
    """Connect to WeConnect and listen to events"""
    logger.info("> Initialize WeConnect")
    connection = weconnect.WeConnect(
        username=args.vwusername,
        password=args.vwpassword,
        updateAfterLogin=False,
        loginOnInit=False,
    )
    logger.info("> Login to WeConnect")
    connection.login()
    logger.info("> Register for events")
    event_handler = create_event_handler(args)
    connection.addObserver(
        event_handler,
        addressable.AddressableLeaf.ObserverEvent.VALUE_CHANGED,
    )
    while True:
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
                    logger.info("> Climatization is off.")
                    asyncio.create_task(toggle_smart_charging(args))
                case ClimatizationStatus.ClimatizationState.INVALID:
                    logger.debug("> Invalid climatization state.")
                case ClimatizationStatus.ClimatizationState.UNKNOWN:
                    logger.debug("> Unknown climatization state.")
                case _:
                    logger.info("> Climatization is on.")
                    asyncio.create_task(toggle_smart_charging(args))

    return event_handler


async def toggle_smart_charging(args) -> None:
    """Toggle smart charging mode"""
    logger.debug("> Logging in to Easee.")
    easee = Easee(args.easeeusername, args.easeepassword)
    logger.debug("> Success!")
    sites = await easee.get_sites()
    home = sites[0]
    circuits = home.get_circuits()
    the_circuit = circuits[0]
    chargers = the_circuit.get_chargers()
    the_charger = chargers[0]
    state = await the_charger.get_state()
    logging.debug(f"> State of the charger: {state}")
    if state["smartCharging"] and state["chargerOpMode"] == "AWAITING_START":
        logger.info("> Turning off smart charging.")
        await the_charger.smart_charging(False)

    elif state["smartCharging"] is False:
        logger.info("> Turning on smart charging.")
        await the_charger.smart_charging(True)
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
    parser.add_argument(
        "-tl",
        "--timerlogs",
        help="Suppress logging from timers",
        default=True,
        required=False,
        type=bool,
    )
    parser.add_argument(
        "-l",
        "--loglevel",
        help="Set the loglevel",
        default="INFO",
        required=False,
        type=str,
    )
    args = parser.parse_args()

    # The weconnect library can be a bit noisy.
    if args.timerlogs:
        LOG.disabled = True

    # Set the logging level
    logger.setLevel(args.loglevel)

    await asyncio.gather(asyncio.create_task(weconnect_listener(args)))


# Run the main function
asyncio.run(main())
