import difflib

class SearchService:
    def __init__(self):
        # The similarity threshold (0.0 to 1.0)
        self.threshold = 0.4

    def filter_data(self, query, data_list, key_to_search="name"):
        """
        Filters a list of dictionaries based on a query string.
       
        """
        if not query:
            return data_list

        query = query.lower()
        results = []

        for item in data_list:
            # Get the value to compare (e.g., 'name' or 'app_name')
            target_value = item.get(key_to_search, "").lower()
            
            # Simple substring match first for speed
            if query in target_value:
                results.append(item)
                continue
            
            # Fuzzy matching for typos
            similarity = difflib.SequenceMatcher(None, query, target_value).ratio()
            if similarity >= self.threshold:
                results.append(item)

        return results