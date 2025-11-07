import json
from logging import getLogger

from conda.common.serialize.json import loads as json_load
from conda.models.records import PrefixRecord
from conda.exceptions import CorruptedEnvironmentError

log = getLogger(__name__)


# Modified version of conda.core.prefix_data.PrefixData::_load_single_record
def _load_single_record(self, prefix_record_json_path):
    log.debug("loading prefix record %s", prefix_record_json_path)
    with open(prefix_record_json_path) as fh:
        try:
            json_data = json_load(fh.read())
        except (UnicodeDecodeError, json.JSONDecodeError):
            # UnicodeDecodeError: catch horribly corrupt files
            # JSONDecodeError: catch bad json format files
            raise CorruptedEnvironmentError(self.prefix_path, prefix_record_json_path)

        # TODO: consider, at least in memory, storing prefix_record_json_path as part
        #       of PrefixRecord
        prefix_record = PrefixRecord(**json_data)

        # Skip this check since it will likely fail for whl based packages
        """
        # check that prefix record json filename conforms to name-version-build
        # apparently implemented as part of #2638 to resolve #2599
        try:
            n, v, b = basename(prefix_record_json_path)[:-5].rsplit("-", 2)
            if (n, v, b) != (
                prefix_record.name,
                prefix_record.version,
                prefix_record.build,
            ):
                raise ValueError()
        except ValueError:
            log.warning(
                "Ignoring malformed prefix record at: %s", prefix_record_json_path
            )
            # TODO: consider just deleting here this record file in the future
            return
        """

        # self.__prefix_records[prefix_record.name] = prefix_record
        # name mangled version as this is used out of the class scope
        self._PrefixData__prefix_records[prefix_record.name] = prefix_record
