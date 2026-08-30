"""
Plugin Class :: GIGABYTE (AMI MegaRAC SP-X) Redfish interaction

Standards-based behaviour from default.py, plus the one thing the standard cannot
answer: what this BMC's multipart firmware push must carry beyond the two parts
the specification names. Measured on a GIGABYTE R181-Z91, BMC 12.61.25, against
/redfish/v1/UpdateService/upload:

  - the standard two-part form gets no answer at all; the connection sits open
    until the client gives up
  - @Redfish.OperationApplyTime in UpdateParameters is refused
  - a third part, OemParameters, is required, and it must carry ImageType - the
    component being flashed, as the board's own inventory names it (BMC, BIOS)

Every one of those was learned from the board's rejection of the previous attempt,
which is why it lives here rather than being discovered: the board only says what
it wants after the image has been sent.
"""

__author__      = 'Antoine Schonewille'
__copyright__   = 'Copyright 2026, Luna2 Project'
__license__     = 'GPL'
__version__     = '2.2'
__maintainer__  = 'Antoine Schonewille'
__email__       = 'antoine.schonewille@clustervision.com'
__status__      = 'Development'

from plugins.redfish.default import Plugin as Default


class Plugin(Default):
    """
    GIGABYTE boards carry AMI MegaRAC; the multipart push needs OemParameters.
    """

    def multipart(self, component=None, filename=None):
        """
        OemParameters names the image type, which for this firmware is the
        component. Without it the board demands it; with anything else it refuses.
        """
        return {'OemParameters': {'ImageType': component or 'BMC'}}, filename
