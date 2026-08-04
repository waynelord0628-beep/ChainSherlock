from crypto_investigator.investigation.investigation_result import RelationshipResult


def analyze_relationships(analysis_by_target) -> RelationshipResult:
    targets = sorted(analysis_by_target)
    counterparties = {
        target: {item.address for item in analysis_by_target[target].counterparties}
        for target in targets
    }
    sources = {
        target: {
            edge.source for edge in analysis_by_target[target].flow.edges
            if edge.target.casefold() == target.casefold()
        }
        for target in targets
    }
    destinations = {
        target: {
            edge.target for edge in analysis_by_target[target].flow.edges
            if edge.source.casefold() == target.casefold()
        }
        for target in targets
    }

    def common(groups):
        result = {}
        for index, first in enumerate(targets):
            for second in targets[index + 1:]:
                shared = tuple(sorted(groups[first] & groups[second], key=str.casefold))
                if shared:
                    result[f"{first}|{second}"] = shared
        return result

    return RelationshipResult(common(counterparties), common(sources), common(destinations))
