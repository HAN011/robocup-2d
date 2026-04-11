from lib.action.neck_scan_field import NeckScanField
from lib.action.scan_field import ScanField
from lib.debug.level import Level
from pyrusgeom.angle_deg import AngleDeg
from base.strategy_formation import StrategyFormation

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from lib.player.player_agent import PlayerAgent
class Bhv_BeforeKickOff:
    MOVE_RETRY_CYCLES = 6

    def __init__(self):
        pass

    @staticmethod
    def _should_issue_move(agent: 'PlayerAgent', target):
        current_cycle = agent.world().time().cycle()
        last_target = getattr(agent, "_aurora_before_kickoff_move_target", None)
        last_cycle = getattr(agent, "_aurora_before_kickoff_move_cycle", -Bhv_BeforeKickOff.MOVE_RETRY_CYCLES)

        if last_target is None or last_target.dist(target) > 0.2:
            setattr(agent, "_aurora_before_kickoff_move_target", target.copy())
            setattr(agent, "_aurora_before_kickoff_move_cycle", current_cycle)
            return True

        if current_cycle - last_cycle >= Bhv_BeforeKickOff.MOVE_RETRY_CYCLES:
            setattr(agent, "_aurora_before_kickoff_move_cycle", current_cycle)
            return True

        return False

    def execute(self, agent: 'PlayerAgent'):
        unum = agent.world().self().unum()
        st = StrategyFormation.i()
        target = st.get_pos(unum)
        if target.dist(agent.world().self().pos()) > 1.:
            if self._should_issue_move(agent, target):
                agent.do_move(target.x(), target.y())
            agent.set_neck_action(NeckScanField())
            return True
        ScanField().execute(agent)
        return True
