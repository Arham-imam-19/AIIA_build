// Role -> screen. The token decides which one renders; there is no way to ask
// for another role's dashboard, because the role is not a parameter anywhere.

import Coordinator from './Coordinator'
import Ethics from './Ethics'
import Investigator from './Investigator'
import Regulator from './Regulator'
import Sponsor from './Sponsor'

export const DASHBOARDS = {
  principal_investigator: Investigator,
  coordinator: Coordinator,
  sponsor: Sponsor,
  ethics_committee: Ethics,
  regulator: Regulator,
  // An admin exists to run the system, not the study. They get the regulator's
  // all-seeing read-only view, which is the closest honest match.
  admin: Regulator,
}

export const FALLBACK = Sponsor
