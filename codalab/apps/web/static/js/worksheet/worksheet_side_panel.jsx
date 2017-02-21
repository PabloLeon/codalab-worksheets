/*
Shows the side panel which contains information about the current bundle or
worksheet (with the focus).
*/

var WorksheetSidePanel = React.createClass({
    getInitialState: function() {
        return {};
    },

    componentDidMount: function(e) {
        var self = this;
        $('#dragbar_vertical').mousedown(function(e) {
            self.resizePanel(e);
        });
        $(document).mouseup(function(e) {
            $(this).unbind('mousemove');
        });
        $(window).resize(function(e) {
            self.resetPanel();
        });
        this.debouncedRefreshBundleSidePanel = _.debounce(this.refreshBundleSidePanel, 200).bind(this);
        

        var getWorksheet = function() {
 //         if (this.state.worksheet_info) {
 //           this.setState({
 //             worksheet_info: null
 //           });
 //         }
          var worksheet_info = this.getWorksheetInfo(this.getFocus());

          var onSuccess = function(data, status, jqXHR) {
              // TODO figure out what data looks like and then add permission_str, or everything, into this.getWorksheetInfo(focus)
  //            debugger; // 
            //  this.setState({
            //    worksheet_info: data
            //  });
            debugger;
          }.bind(this);

          var onError = function(jqXHR, status, error) {
              console.error(jqXHR.responseText);
              // TODO try again? Show error message?
          }.bind(this);

          $.ajax({
              url: '/rest/api/worksheets/' + worksheet_info.uuid + '/', // TODO
              type: 'GET',
              success: onSuccess,
              error: onError
          });
        }
        this.refreshWorksheets = _.debounce(getWorksheet, 300).bind(this);
        
    },

    // TODO
    refreshBundleSidePanel: function() {
      /*
      var focus = this.getFocus();
      var worksheet_info;
//      debugger;
      if (focus) {
          worksheet_info = this.getWorksheetInfo(focus);
//          debugger;
      } 
      if (focus && this.isFocusWorksheet(focus)) {
        if (this.state.worksheet_info) {
          this.setState({
            worksheet_info: null
          });
        }

      } */
      debugger;
      if (this.refs.hasOwnProperty('bundle_info_side_panel')) {
        this.refs.bundle_info_side_panel.refreshBundle();
      }
    },

    componentDidUpdate: function() {
      // TODO
      this.refreshWorksheets();
      this.debouncedRefreshBundleSidePanel();
    },

    getFocus: function() {
        return getFocusFromWorksheet(this.props.ws, this.props.focusIndex);


        // Return the state to show on the side panel
        var info = this.props.ws.info;
        if (!info) return null;
        if (this.props.focusIndex == -1)  // Not focus on anything, show worksheet
          return info;
        return info.items[this.props.focusIndex];
    },

    // What kind of thing is it?
    isFocusWorksheet: function(focus) {
      return focus.mode === undefined || focus.mode == 'worksheet' || focus.mode == 'wsearch';
    },
    isFocusMarkup: function(focus) {
      // If search and didn't return bundles, then count as markup
      return focus.mode == 'markup' || (focus.mode == 'search' && (!focus.interpreted.items[0] || focus.interpreted.items[0].bundle_info === undefined));
    },
    isFocusBundle: function(focus) {
      return !this.isFocusWorksheet(focus) && !this.isFocusMarkup(focus);
    },
    getBundleInfo: function(focus) {
      if (focus.mode == 'table')  // Drill down into row of table
          return this.props.subFocusIndex != -1 ? focus.bundle_info[this.props.subFocusIndex] : null;
      else if (focus.mode == 'search')
          return this.props.subFocusIndex != -1 ? focus.interpreted.items[0].bundle_info[this.props.subFocusIndex] : null;
      else
          return focus.bundle_info;
    },
    getWorksheetInfo: function(focus) {
      if (focus.mode == 'worksheet')
        return focus.subworksheet_info;
      else if (focus.mode == 'wsearch') {
        if (this.props.subFocusIndex == -1)
          return null;
        var item = focus.interpreted.items[this.props.subFocusIndex];
        return item ? item.subworksheet_info : null;
      }
      else
        return focus;
    },

    resizePanel: function(e) {
        e.preventDefault();
        $(document).mousemove(function(e) {
            var windowWidth = $(window).width();
            var panelWidth = windowWidth - e.pageX;
            var panelWidthPercentage = (windowWidth - e.pageX) / windowWidth * 100;
            if (240 < panelWidth && panelWidthPercentage < 55) {
                $('.ws-container').css('width', e.pageX);
                $('.ws-panel').css('width', panelWidthPercentage + '%');
                $('#dragbar_vertical').css('right', panelWidthPercentage + '%');
            }
        });
    },
    resetPanel: function() {
        var windowWidth = $(window).width();
        if (windowWidth < 768) {
            $('.ws-container').removeAttr('style');
        } else {
            var panelWidth = parseInt($('.ws-panel').css('width'));
            var containerWidth = windowWidth - panelWidth;
            $('.ws-container').css('width', containerWidth);
        }
    },

    render: function() {
        //console.log('WorksheetSidePanel.render');

        var bundle_uploader = <BundleUploader
          ws={this.props.ws}
          refreshWorksheet={this.props.bundleMetadataChanged}
        />;

        var run_bundle_builder = <RunBundleBuilder
          ws={this.props.ws}
          escCount={this.props.escCount}
        />;

        var new_worksheet = <NewWorksheet
          escCount={this.props.escCount}
          userInfo={this.props.userInfo}
        />;

        var focus = this.getFocus();
        var side_panel_details = '';
        if (focus) {
          if (this.isFocusWorksheet(focus)) {
            // Show worksheet (either main worksheet or subworksheet)
            var worksheet_info = this.state.worksheet_info ? this.state.worksheet_info : this.getWorksheetInfo(focus);

            side_panel_details = <WorksheetDetailSidePanel
                                   key={'ws' + this.props.focusIndex}
                                   worksheet_info={worksheet_info}
                                   bundleMetadataChanged={this.props.bundleMetadataChanged}
                                 />;
          } else if (this.isFocusMarkup(focus)) {
            // Show nothing (maybe later show markdown just for fun?)
          } else if (this.isFocusBundle(focus)) {
            // Show bundle (either full bundle or row in table)
            var bundle_info = this.getBundleInfo(focus);
            if (bundle_info) {
              side_panel_details = <Bundle
                                     key={'table' + this.props.focusIndex + ',' + this.props.subFocusIndex}
                                     bundle_uuid={bundle_info.uuid}
                                     bundleMetadataChanged={this.props.bundleMetadataChanged}
                                     ref="bundle_info_side_panel"
                                   />;
            }
          } else {
            console.error('Unknown mode: ' + focus.mode);
          }
        }

        return (
          <div className="ws-panel">
            <div className='ws-button-group'>
              {bundle_uploader}
              {run_bundle_builder}
              {new_worksheet}
            </div>
              {side_panel_details}
          </div>
        );
    }
});

////////////////////////////////////////////////////////////

// When selecting a worksheet.
var WorksheetDetailSidePanel = React.createClass({
    getInitialState: function() {
        return { };
    },

    render: function() {
      // Select the current worksheet or the subworksheet.
      var worksheet = this.props.worksheet_info;
      if (!worksheet) return <div />;

      // Show brief summary of contents.
      var rows = [];
      if (worksheet.items) {
        worksheet.items.forEach(function(item) {
          if (item.bundle_info) {
            // Show bundle
            var bundle_infos = item.bundle_info;
            if (!(bundle_infos instanceof Array))
              bundle_infos = [bundle_infos];

            bundle_infos.forEach(function(b) {
              var url = "/bundles/" + b.uuid;
              var short_uuid = shorten_uuid(b.uuid);
              rows.push(<tr>
                <td>{b.bundle_type}</td>
                <td><a href={url} target="_blank">{b.metadata.name}({short_uuid})</a></td>
              </tr>);
            });
          } else if (item.mode == 'worksheet') {
            // Show worksheet
            var info = item.subworksheet_info;
            var title = info.title || info.name;
            var url = '/worksheets/' + info.uuid;
            rows.push(<tr>
              <td>worksheet</td>
              <td><a href={url} target="_blank">{title}</a></td>
            </tr>);
          }
        });
      }

      var bundles_html = (
        <div className="bundles-table">
            <table className="bundle-meta table">
                <thead>
                  <tr>
                    <th>type</th>
                    <th>name</th>
                  </tr>
                </thead>
                <tbody>
                  {rows}
                </tbody>
            </table>
        </div>
      );

      return (
          <div id="panel_content">
              <table className="bundle-meta table">
                <tr><th>uuid</th><td>{worksheet.uuid}</td></tr>
                <tr><th>name</th><td><WorksheetEditableField canEdit={true} fieldName="name" value={worksheet.name} uuid={worksheet.uuid} onChange={this.props.bundleMetadataChanged} /></td></tr>
                <tr><th>title</th><td><WorksheetEditableField canEdit={true} fieldName="title" value={worksheet.title} uuid={worksheet.uuid} onChange={this.props.bundleMetadataChanged} /></td></tr>
                <tr><th>owner</th><td>{worksheet.owner_name}</td></tr>
                <tr><th>permissions</th><td>{render_permissions(worksheet)}</td></tr>
              </table>
              {bundles_html}
          </div>
      );
    }
});
