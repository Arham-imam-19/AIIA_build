// Role -> screen. The token decides which one renders; there is no way to ask
// for another role's dashboard, because the role is not a parameter anywhere.

import Coordinator from './Coordinator'
import Ethics from './Ethics'
import InstitutionAdmin from './InstitutionAdmin'
import Investigator from './Investigator'
import Patient from './Patient'
import Regulator from './Regulator'
import Sponsor from './Sponsor'
import Monitor from './Monitor'
import Pharmacovigilance from './Pharmacovigilance'
import DSMB from './DSMB'

export const DASHBOARDS = {
  admin: Regulator,
  institution_admin: InstitutionAdmin,
  principal_investigator: Investigator,
  coordinator: Coordinator,
  patient: Patient,
  sponsor: Sponsor,
  ethics_committee: Ethics,
  regulator: Regulator,
  monitor: Monitor,
  pharmacovigilance: Pharmacovigilance,
  dsmb: DSMB,
}

export const FALLBACK = Sponsor
